import asyncio
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import errors, types

import test_graph_tools
from app.agents.base import BaseAgent
from app.agents.investigation import InvestigationAgent
from app.agents.investigation.demo import DemoInvestigationClient
from app.agents.investigation.schemas import ToolStep
from app.agents.investigation.workflow import validate_submission
from app.main import create_app
from app.services.gemini_client import GeminiToolClient, to_gemini_messages
from app.services.tool_llm import ModelTurn, ToolCall, ToolMessage, UnconfiguredToolLLMClient
from app.types.schemas import AgentContext


def turn(identifier, name, arguments):
    return ModelTurn(tool_calls=[ToolCall(id=identifier, name=name, arguments=arguments)])


def submission(source="read-1", **changes):
    return {"verdict": "benign", "confidence": 0.6, "members": [], "victims": [],
            "evidence": [{"claim": "Reviewed application data", "source": source}],
            "benign_explanation": "Considered legitimate shared-device usage", **changes}


class ScriptedClient:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.history = []
        self.offered_tools = []

    def ensure_ready(self):
        pass

    async def complete(self, messages, tools):
        self.history.append(copy.deepcopy(messages))
        self.offered_tools.append([tool["name"] for tool in tools])
        return next(self.responses)


class InvestigationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = test_graph_tools.GraphToolTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.database = self.fixture.database

    def agent(self, client, **options):
        return InvestigationAgent(client, database=self.database, **options)

    async def test_inherits_base_and_finishes_with_valid_evidence(self):
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                turn("finish", "submit_case", submission()))
        agent = self.agent(client)
        self.assertIsInstance(agent, BaseAgent)
        result = await agent.investigate("A", AgentContext(conversation_id="conv"))
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.case.verdict, "benign")
        self.assertEqual(result.conversation_id, "conv")
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(client.history[1][-1].tool_call_id, "read-1")
        self.assertEqual(json.loads(client.history[1][-1].content)["tool_call_id"], "read-1")

    async def test_invalid_evidence_can_be_repaired(self):
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                turn("bad", "submit_case", submission("invented")),
                                turn("finish", "submit_case", submission()))
        result = await self.agent(client).investigate("A")
        self.assertEqual(result.status, "completed")
        self.assertFalse(result.steps[1].result["ok"])
        self.assertEqual(result.steps[1].result["available_evidence_sources"], ["read-1"])
        self.assertEqual(result.case.evidence[0].source, "read-1")

    async def test_schema_feedback_identifies_fields_without_echoing_values(self):
        invalid = submission(confidence=2, api_key="secret-token")
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                turn("bad", "submit_case", invalid),
                                turn("finish", "submit_case", submission()))
        result = await self.agent(client).investigate("A")
        feedback = result.steps[1].result
        self.assertEqual(result.status, "completed")
        self.assertEqual({item["field"] for item in feedback["error"]["fields"]}, {"confidence", "api_key"})
        self.assertNotIn("secret-token", json.dumps(feedback))

    async def test_root_schema_feedback_explains_missing_members(self):
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                turn("bad", "submit_case", submission(verdict="fraud_ring", members=[])),
                                turn("finish", "submit_case", submission(verdict="fraud_ring", members=["A"])))
        result = await self.agent(client).investigate("A")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.case.verdict, "fraud_ring")
        self.assertIn("requires members", result.steps[1].result["error"]["fields"][0]["message"])

    async def test_failed_tool_cannot_be_used_as_evidence(self):
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "missing"}),
                                turn("bad", "submit_case", submission()))
        result = await self.agent(client, max_tool_calls=2).investigate("A")
        self.assertEqual(result.status, "limit_reached")
        self.assertEqual(result.case.verdict, "inconclusive")
        self.assertEqual(result.case.evidence, [])

    async def test_unknown_members_and_overlap_are_rejected(self):
        for fields in ({"verdict": "fraud_ring", "members": ["missing"]},
                       {"verdict": "fraud_ring", "members": ["A"], "victims": ["A"]}):
            client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                    turn("bad", "submit_case", submission(**fields)))
            result = await self.agent(client, max_tool_calls=2).investigate("A")
            self.assertEqual(result.case.verdict, "inconclusive")
            self.assertEqual(result.steps[-1].result["error"]["code"], "invalid_case")

    async def test_budget_stops_after_twelve_calls(self):
        client = ScriptedClient(*(turn(str(index), "get_application", {"app_id": "A"}) for index in range(12)))
        result = await self.agent(client).investigate("A")
        self.assertLessEqual(len(result.steps), 12)
        self.assertEqual(len(client.history), 12)
        self.assertEqual(client.offered_tools[-1], ["submit_case"])
        self.assertEqual(result.reason, "max_tool_calls_reached")
        self.assertEqual(result.case.confidence, 0)

    async def test_terminal_submission_on_last_budget_slot_is_accepted(self):
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                turn("finish", "submit_case", submission()))
        self.assertEqual((await self.agent(client, max_tool_calls=2).investigate("A")).status, "completed")

    async def test_batch_over_budget_is_rejected_before_execution(self):
        response = ModelTurn(tool_calls=[ToolCall(id=str(index), name="get_application", arguments={"app_id": "A"})
                                        for index in range(3)])
        result = await self.agent(ScriptedClient(response), max_tool_calls=2).investigate("A")
        self.assertEqual(result.reason, "max_tool_calls_reached")
        self.assertEqual(result.steps, [])

    async def test_parallel_requests_are_executed_with_matching_results(self):
        batch = ModelTurn(tool_calls=[ToolCall(id="read-1", name="get_application", arguments={"app_id": "A"}),
                                      ToolCall(id="read-2", name="money_flow", arguments={"app_id": "A"})])
        client = ScriptedClient(batch, turn("finish", "submit_case", submission("read-2")))
        result = await self.agent(client).investigate("A")
        self.assertEqual(result.status, "completed")
        tool_messages = [message for message in client.history[-1] if message.role == "tool"]
        self.assertEqual([message.tool_call_id for message in tool_messages], ["read-1", "read-2"])

    async def test_duplicate_ids_and_mixed_terminal_batch_fail_closed(self):
        for batch in ([ToolCall(id="same", name="neighbors", arguments={"node_id": "app:A"})] * 2,
                      [ToolCall(id="end", name="submit_case", arguments=submission()),
                       ToolCall(id="read", name="get_application", arguments={"app_id": "A"})]):
            result = await self.agent(ScriptedClient(ModelTurn(tool_calls=batch))).investigate("A")
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.case.verdict, "inconclusive")
            self.assertEqual(result.steps, [])

    async def test_reused_id_across_turns_fails(self):
        response = turn("same", "get_application", {"app_id": "A"})
        result = await self.agent(ScriptedClient(response, response)).investigate("A")
        self.assertEqual(result.reason, "reused_tool_call_id")
        self.assertEqual(len(result.steps), 1)

    async def test_free_text_without_submission_does_not_become_a_verdict(self):
        result = await self.agent(ScriptedClient(ModelTurn(text="Definitely fraud"))).investigate("A")
        self.assertEqual(result.reason, "model_did_not_call_tool")
        self.assertEqual(result.case.verdict, "inconclusive")

    async def test_unknown_tool_error_is_returned_to_model(self):
        client = ScriptedClient(turn("bad", "execute_sql", {}),
                                turn("finish", "submit_case", submission(verdict="inconclusive", evidence=[])))
        result = await self.agent(client).investigate("A")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.steps[0].result["error"]["code"], "unknown_tool")

    async def test_reported_victim_cannot_be_submitted_as_an_offender(self):
        for data in ({"application": {"app_id": "A"}, "victim_self_report_count": 1},
                     {"reports": [{"reporter_is_victim": True, "reporter_app_ids": ["A"]}]}):
            steps = [ToolStep(tool_call_id="read-1", name="get_application", result={"ok": True, "data": data})]
            with self.assertRaises(ValueError):
                validate_submission(submission(verdict="fraud_ring", members=["A"]), steps)

    async def test_cluster_context_is_passed_without_overriding_system_instructions(self):
        client = ScriptedClient(turn("read-1", "get_application", {"app_id": "A"}),
                                turn("finish", "submit_case", submission()))
        result = await self.agent(client).investigate("A", AgentContext(metadata={"cluster_id": "cluster-1"},
                                                                       system_prompt="UNTRUSTED-OVERRIDE"))
        self.assertEqual(result.status, "completed")
        self.assertIn("cluster-1", client.history[0][1].content)
        self.assertNotIn("UNTRUSTED-OVERRIDE", client.history[0][0].content)

    async def test_timeout_and_caller_cancellation_propagate(self):
        started, stopped = asyncio.Event(), asyncio.Event()
        class SlowClient:
            def ensure_ready(self):
                pass
            async def complete(self, messages, tools):
                started.set()
                try:
                    await asyncio.sleep(60)
                finally:
                    stopped.set()
        result = await self.agent(SlowClient(), operation_timeout=0.01).investigate("A")
        self.assertEqual(result.reason, "operation_timeout")
        self.assertTrue(stopped.is_set())
        started.clear()
        stopped.clear()
        task = asyncio.create_task(self.agent(SlowClient()).investigate("A"))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(stopped.is_set())

    async def test_stream_emits_each_tool_and_only_one_final_result(self):
        agent = self.agent(DemoInvestigationClient())
        events = [event async for event in agent.stream("A", AgentContext())]
        self.assertTrue(events[0].startswith("event: started"))
        self.assertEqual(sum(event.startswith("event: done") for event in events), 1)
        self.assertEqual(sum(event.startswith("event: tool_result") for event in events), 5)
        self.assertNotIn("Private address", "".join(events))
        self.assertNotIn("0900000001", "".join(events))

    async def test_concurrent_runs_keep_aliases_and_evidence_separate(self):
        agent = self.agent(DemoInvestigationClient())
        a, b = await asyncio.gather(agent.investigate("A"), agent.investigate("B"))
        self.assertEqual((a.status, b.status), ("completed", "completed"))
        self.assertNotEqual(a.run_id, b.run_id)
        self.assertNotEqual(a.steps[0].result["data"]["application"]["device_node_id"],
                            b.steps[0].result["data"]["application"]["device_node_id"])


class InvestigationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_graph_tools.GraphToolTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_json_and_sse_requests_need_no_agent_id(self):
        app = create_app(tool_llm_client=DemoInvestigationClient(), graph_database=self.fixture.database)
        with TestClient(app) as client:
            response = client.post("/api/investigations", json={"app_id": "A"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["case"]["verdict"], "inconclusive")
            response = client.post("/api/investigations", json={"app_id": "A", "streamResponse": True})
            self.assertEqual(response.status_code, 200)
            self.assertIn("event: done", response.text)
            self.assertEqual(client.post("/api/investigations", json={"app_id": "A", "agent_id": "x"}).status_code, 422)

    def test_missing_client_or_database_returns_503_before_stream(self):
        for client, database in [(UnconfiguredToolLLMClient(), self.fixture.database),
                                 (DemoInvestigationClient(), self.fixture.directory / "missing.db")]:
            with TestClient(create_app(tool_llm_client=client, graph_database=database)) as application:
                response = application.post("/api/investigations", json={"app_id": "A", "streamResponse": True})
                self.assertEqual(response.status_code, 503)


class GeminiAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_provider_error_is_retried_but_bad_request_is_not(self):
        response = types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(text="OK")]), finish_reason="STOP",
        )])
        for failure, expected in [(errors.ServerError(503, {"error": {"message": "busy"}}), 2),
                                  (errors.ClientError(400, {"error": {"message": "bad request"}}), 1)]:
            api = SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock(side_effect=[failure, response])))
            context = AsyncMock()
            context.__aenter__.return_value = api
            with patch("app.services.gemini_client.genai.Client", return_value=SimpleNamespace(aio=context)), \
                 patch("app.services.gemini_client.asyncio.sleep", new_callable=AsyncMock):
                client = GeminiToolClient(api_key="test", model="test", min_interval=0)
                if expected == 1:
                    with self.assertRaises(errors.ClientError):
                        await client.complete([ToolMessage(role="user", content="test")], [])
                else:
                    self.assertEqual((await client.complete([ToolMessage(role="user", content="test")], [])).text, "OK")
            self.assertEqual(api.models.generate_content.call_count, expected)

    async def test_adapter_keeps_signatures_and_disables_automatic_execution(self):
        content = types.Content(role="model", parts=[types.Part(
            function_call=types.FunctionCall(id="call-1", name="get_application", args={"app_id": "A"}),
            thought_signature=b"signature-bytes",
        )])
        response = types.GenerateContentResponse(candidates=[types.Candidate(content=content, finish_reason="STOP")])
        api = SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock(return_value=response)))
        context = AsyncMock()
        context.__aenter__.return_value = api
        with patch("app.services.gemini_client.genai.Client", return_value=SimpleNamespace(aio=context)):
            client = GeminiToolClient(api_key="test-key", model="test-model")
            result = await client.complete([ToolMessage(role="user", content="test")], [
                {"name": "get_application", "description": "Read", "parameters": {"type": "object"}},
            ])
        config = api.models.generate_content.call_args.kwargs["config"]
        self.assertTrue(config.automatic_function_calling.disable)
        self.assertEqual(result.tool_calls[0].id, "call-1")
        history = [ToolMessage(role="assistant", tool_calls=result.tool_calls, provider_content=result.provider_content),
                   ToolMessage(role="tool", tool_call_id="call-1", content=json.dumps({"ok": True}))]
        _, converted = to_gemini_messages(history)
        self.assertEqual(converted[0].parts[0].thought_signature, b"signature-bytes")
        self.assertEqual(converted[1].parts[0].function_response.id, "call-1")

    async def test_parallel_results_share_one_user_message_and_preserve_ids(self):
        calls = [ToolCall(id=str(index), name="neighbors", arguments={}) for index in range(2)]
        history = [ToolMessage(role="system", content="instructions"),
                   ToolMessage(role="assistant", tool_calls=calls),
                   *(ToolMessage(role="tool", tool_call_id=call.id, content=json.dumps({"ok": False})) for call in calls)]
        system, contents = to_gemini_messages(history)
        self.assertEqual(system, "instructions")
        self.assertEqual(len(contents), 2)
        self.assertEqual([part.function_response.id for part in contents[1].parts], ["0", "1"])


if __name__ == "__main__":
    unittest.main()
