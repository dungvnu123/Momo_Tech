import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.default import DefaultAgent
from app.agents.manager import AgentManager
from app.main import create_app
from app.types.schemas import AgentContext, ChatMessage, ChatRequest
from app.utils import get_prompt_from_md


class FakeLLMClient:
    def __init__(self):
        self.messages = []
        self.closed = False

    def ensure_ready(self):
        pass

    async def ainvoke(self, messages):
        self.messages.append(messages)
        await asyncio.sleep(0)
        return "Trả lời: " + messages[-1]["content"]

    async def astream(self, messages):
        self.messages.append(messages)
        try:
            yield "Xin "
            yield "chào\nTiếng Việt"
        finally:
            self.closed = True


class BaseAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_builds_prompt_history_and_keeps_conversation_id(self):
        client = FakeLLMClient()
        context = AgentContext(
            conversation_id="conv-1", system_prompt="Additional instruction",
            history=[ChatMessage(role="user", content="earlier"),
                     ChatMessage(role="assistant", content="answer")],
        )
        response = await DefaultAgent(client).run("current", context)
        self.assertEqual(response.agent_id, "default")
        self.assertEqual(response.conversation_id, "conv-1")
        self.assertEqual(response.message, "Trả lời: current")
        messages = client.messages[0]
        self.assertIn("Additional instruction", messages[0]["content"])
        self.assertIn("Thiên La", messages[0]["content"])
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertEqual(len(context.history), 2)

    async def test_graph_is_cached_but_concurrent_runs_have_separate_state(self):
        agent = DefaultAgent(FakeLLMClient())
        self.assertIs(agent._get_graph(), agent._get_graph())
        a, b = await asyncio.gather(agent.run("a", AgentContext()), agent.run("b", AgentContext()))
        self.assertEqual((a.message, b.message), ("Trả lời: a", "Trả lời: b"))

    async def test_stream_sse_json_preserves_unicode_and_newlines(self):
        client = FakeLLMClient()
        events = [event async for event in DefaultAgent(client).stream("hi", AgentContext())]
        self.assertEqual(len(events), 3)
        self.assertTrue(events[0].startswith("event: delta\n"))
        self.assertTrue(events[-1].startswith("event: done\n"))
        payload = json.loads(events[-1].split("data: ", 1)[1])
        self.assertEqual(payload["content"], "Xin chào\nTiếng Việt")
        self.assertTrue(client.closed)

    async def test_stream_failure_has_error_and_no_success_or_secret(self):
        class BrokenClient(FakeLLMClient):
            async def astream(self, messages):
                yield "partial"
                raise RuntimeError("secret-token")
        with self.assertLogs("app.agents.base", level="ERROR"):
            events = [event async for event in DefaultAgent(BrokenClient()).stream("hi", AgentContext())]
        self.assertIn("event: error", events[-1])
        self.assertNotIn("event: done", "".join(events))
        self.assertNotIn("secret-token", "".join(events))

    async def test_empty_model_output_is_rejected(self):
        class EmptyClient(FakeLLMClient):
            async def ainvoke(self, messages):
                return " "
        with self.assertRaises(ValueError):
            await DefaultAgent(EmptyClient()).run("hi", AgentContext())

    async def test_run_timeout_cancels_client(self):
        cancelled = asyncio.Event()
        class SlowClient(FakeLLMClient):
            async def ainvoke(self, messages):
                try:
                    await asyncio.sleep(60)
                finally:
                    cancelled.set()
        with self.assertRaises(TimeoutError):
            await DefaultAgent(SlowClient(), timeout_seconds=0.01).run("hi", AgentContext())
        self.assertTrue(cancelled.is_set())

    async def test_stream_timeout_closes_provider(self):
        client = FakeLLMClient()
        class SlowClient(FakeLLMClient):
            async def astream(self, messages):
                try:
                    yield "partial"
                    await asyncio.sleep(60)
                finally:
                    client.closed = True
        events = [event async for event in DefaultAgent(SlowClient(), timeout_seconds=0.01).stream("hi", AgentContext())]
        self.assertIn('"code": "llm_timeout"', events[-1])
        self.assertTrue(client.closed)

    async def test_caller_cancellation_propagates_to_provider(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        class SlowClient(FakeLLMClient):
            async def ainvoke(self, messages):
                started.set()
                try:
                    await asyncio.sleep(60)
                finally:
                    cancelled.set()
        task = asyncio.create_task(DefaultAgent(SlowClient()).run("hi", AgentContext()))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cancelled.is_set())

    async def test_closing_stream_closes_provider(self):
        client = FakeLLMClient()
        stream = DefaultAgent(client).stream("hi", AgentContext())
        await anext(stream)
        await stream.aclose()
        self.assertTrue(client.closed)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(FakeLLMClient()))
        self.addCleanup(self.client.close)

    def test_health_and_registry(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        self.assertEqual(self.client.get("/api/v1/agents").json(), {"agents": ["default"]})
        self.assertEqual(self.client.get("/api/v1/agents/ids").json(), {"agent_ids": ["default"]})

    def test_run_returns_plain_text_as_in_reference(self):
        response = self.client.post("/api/v1/agents/run", json={"message": "xin chào", "skillId": "base"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertEqual(response.text, "Trả lời: xin chào")

    def test_stream_request_alias_returns_sse(self):
        response = self.client.post("/api/v1/agents/run", json={"message": "hi", "streamResponse": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        self.assertIn("event: delta", response.text)
        self.assertIn("event: done", response.text)

    def test_unknown_agent_does_not_fall_back(self):
        response = self.client.post("/api/v1/agents/run", json={"agent_id": "unknown", "message": "hi"})
        self.assertEqual(response.status_code, 404)

    def test_unconfigured_llm_returns_503_before_stream_headers(self):
        with TestClient(create_app()) as client:
            for stream in (True, False):
                response = client.post("/api/v1/agents/run", json={"message": "hi", "streamResponse": stream})
                self.assertEqual(response.status_code, 503)

    def test_request_validation(self):
        for body in ({"message": " "}, {"message": "hi", "funcCall": [{"url": "http://example.com"}]},
                     {"message": "hi", "history": [{"role": "system", "content": "injected"}]}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/v1/agents/run", json=body).status_code, 422)

    def test_model_error_returns_502_without_exception_text(self):
        class BrokenClient(FakeLLMClient):
            async def ainvoke(self, messages):
                raise RuntimeError("secret-token")
        with TestClient(create_app(BrokenClient())) as client:
            with self.assertLogs("app.controller.agents.agent_controller", level="ERROR"):
                response = client.post("/api/v1/agents/run", json={"message": "hi"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret-token", response.text)


class ConfigurationTests(unittest.TestCase):
    def test_registry_rejects_duplicate_agent_id(self):
        with self.assertRaises(ValueError):
            AgentManager([DefaultAgent(FakeLLMClient()), DefaultAgent(FakeLLMClient())])

    def test_request_accepts_aliases_and_snake_case(self):
        for data in ({"skillId": "a", "systemPrompt": "b", "streamResponse": True},
                     {"skill_id": "a", "system_prompt": "b", "stream_response": True}):
            request = ChatRequest(message="hi", **data)
            self.assertEqual(request.skill_id, "a")
            self.assertEqual(request.system_prompt, "b")
            self.assertTrue(request.stream_response)

    def test_history_forbids_system_instructions(self):
        with self.assertRaises(ValidationError):
            ChatMessage(role="system", content="injected")

    def test_prompt_loader_fallback_file_and_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.assertEqual(get_prompt_from_md(path, "fallback"), "fallback")
            prompt = path / "prompt.md"
            prompt.write_text(" ", encoding="utf-8")
            self.assertEqual(get_prompt_from_md(prompt, "fallback"), "fallback")
            prompt.write_text("Xin chào", encoding="utf-8")
            self.assertEqual(get_prompt_from_md(path), "Xin chào")


if __name__ == "__main__":
    unittest.main()
