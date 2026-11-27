import asyncio
import copy
import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

import test_graph_tools
from app.ai.evaluation import accuracy, evaluate, select_reports
from app.ai.features import cluster_summary, entity_candidates, entity_record
from app.ai.indicators import canonical_indicator
from app.ai.pipeline import analyze_stored_reports, triage_groups
from app.ai.runner import AIOutputError
from app.ai.schemas import EntityDecision, EntityPair, Indicator, ReportAnalysis, TriageDecision
from app.ai.service import AIService
from app.graph.ai_store import AIStore
from app.graph import build_graph
from app.main import create_app
from app.services.tool_llm import ModelTurn, ToolCall, UnconfiguredToolLLMClient
from app.tools import GraphTools


def report_output(**changes):
    return {"verdict": "scam", "confidence": 0.9, "tactics": ["fee_scam"],
            "indicators": [{"kind": "phone", "raw": "0987654321"}], "reporter_is_victim": True,
            "reasons": ["Requests a verification fee"], "advice": "Do not transfer money", **changes}


class FakeStructuredClient:
    model = "unit-test-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0
        self.inputs = []

    def ensure_ready(self):
        pass

    async def complete(self, messages, tools):
        self.inputs.append(json.loads(messages[1].content))
        output = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return ModelTurn(tool_calls=[ToolCall(id=f"structured-{self.calls}", name=tools[0]["name"],
                                              arguments=copy.deepcopy(output))])


class AITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = test_graph_tools.GraphToolTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.database, self.directory = self.fixture.database, self.fixture.directory

    def pair(self, identifier="p1", left="A", right="B"):
        with AIStore(self.database) as store:
            return EntityPair(pair_id=identifier, left=entity_record(store.application(left)),
                              right=entity_record(store.application(right)))

    async def test_grounded_report_and_cache_avoid_duplicate_api_calls(self):
        client = FakeStructuredClient(report_output())
        service = AIService(client, cache_path=self.directory / "cache.db")
        first = await service.analyze_report("Please call 0987654321")
        second = await service.analyze_report("Please call 0987654321")
        self.assertEqual(first, second)
        self.assertEqual(client.calls, 1)
        self.assertEqual(service.runner.cache_hits, 1)

    async def test_cache_invalidates_for_changed_input_and_model(self):
        client = FakeStructuredClient(report_output())
        service = AIService(client, cache_path=self.directory / "cache.db")
        await service.analyze_report("Call 0987654321")
        await service.analyze_report("Call 0987654321 now")
        client.model = "other-model"
        await service.analyze_report("Call 0987654321")
        self.assertEqual(client.calls, 3)

    async def test_invented_indicator_is_rejected_and_not_cached(self):
        client = FakeStructuredClient(report_output(indicators=[{"kind": "phone", "raw": "0911111111"}]))
        service = AIService(client, cache_path=self.directory / "cache.db")
        with self.assertRaises(AIOutputError):
            await service.analyze_report("Call 0987654321")
        self.assertEqual(client.calls, 2)
        self.assertEqual(service.runner.cache_hits, 0)

    async def test_bank_must_be_grounded_and_aliases_are_canonicalized(self):
        output = report_output(indicators=[{"kind": "bank_account", "raw": "001234567890", "bank": "ACB"}])
        with self.assertRaises(AIOutputError):
            await AIService(FakeStructuredClient(output)).analyze_report("TCB 001234567890")
        self.assertEqual(canonical_indicator(Indicator(kind="bank_account", raw="001234567890", bank="Techcombank")),
                         "account:bank:TCB:001234567890")

    async def test_invalid_cached_output_is_revalidated_and_replaced(self):
        from app import db as pgdb
        cache = self.directory / "cache.db"
        client = FakeStructuredClient(report_output())
        service = AIService(client, cache_path=cache)
        await service.analyze_report("Call 0987654321")
        with pgdb.connect(cache) as connection:
            connection.execute("UPDATE responses SET payload=?", (json.dumps(report_output(confidence=9)),))
        result = await service.analyze_report("Call 0987654321")
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(client.calls, 2)

    async def test_invalid_report_can_be_repaired_once(self):
        client = FakeStructuredClient(report_output(confidence=9), report_output())
        result = await AIService(client).analyze_report("Call 0987654321")
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(client.calls, 2)

    async def test_entity_batch_requires_all_ids_and_rejects_duplicates(self):
        pair = self.pair()
        decision = {"pair_id": "wrong", "decision": "different", "confidence": 0.8, "reason": "Different people"}
        client = FakeStructuredClient({"decisions": [decision]})
        with self.assertRaises(AIOutputError):
            await AIService(client).resolve_entities([pair])
        valid = {**decision, "pair_id": "p1"}
        self.assertEqual((await AIService(FakeStructuredClient({"decisions": [valid]})).resolve_entities([pair])).decisions[0].pair_id, "p1")
        with self.assertRaises(ValueError):
            await AIService(FakeStructuredClient({"decisions": [valid]})).resolve_entities([pair, pair])

    async def test_different_birth_dates_cannot_be_merged(self):
        pair = self.pair().model_dump()
        pair["right"]["dob"] = "1980-01-01"
        client = FakeStructuredClient({"decisions": [{"pair_id": "p1", "decision": "same", "confidence": 0.9, "reason": "Similar name"}]})
        with self.assertRaises(AIOutputError):
            await AIService(client).resolve_entities([pair])

    async def test_triage_requires_exact_cluster_ids(self):
        with AIStore(self.database) as store:
            summary = cluster_summary(store, "c1", ["A", "B"])
        client = FakeStructuredClient({"decisions": [{"cluster_id": "wrong", "decision": "skip", "reason": "Routine"}]})
        with self.assertRaises(AIOutputError):
            await AIService(client).triage([summary])

    async def test_transfer_hold_requires_recipient_warning(self):
        output = {"decision": "hold", "confidence": 0.9, "reasons": ["New recipient"], "advice": "Review"}
        request = {"loan_amount": 1000, "transfer_amount": 900, "minutes_after_disbursal": 10}
        with self.assertRaises(AIOutputError):
            await AIService(FakeStructuredClient(output)).check_transfer(request)
        result = await AIService(FakeStructuredClient(output)).check_transfer({**request, "simo_flag": True})
        self.assertEqual(result.decision, "hold")
        for signal in ({"recipient_ring_senders": 3}, {"customer_says_coached": True}):   # tín hiệu backend mới cũng cho phép hold
            result = await AIService(FakeStructuredClient(output)).check_transfer({**request, **signal})
            self.assertEqual(result.decision, "hold")
        with self.assertRaises(ValueError):   # hợp đồng chặn giá trị sai
            await AIService(FakeStructuredClient(output)).check_transfer({**request, "share_of_balance": 1.5})

    async def test_timeout_propagates(self):
        class Slow(FakeStructuredClient):
            async def complete(self, messages, tools):
                await asyncio.sleep(60)
        service = AIService(Slow(report_output()))
        service.runner.timeout = 0.01
        with self.assertRaises(TimeoutError):
            await service.analyze_report("Call 0987654321")

    async def test_report_pipeline_never_reads_ground_truth(self):
        (self.directory / "ground_truth.json").write_text("invalid json", encoding="utf-8")
        service = AIService(FakeStructuredClient(report_output()))
        results = await analyze_stored_reports(service, self.database, ["R1"])
        self.assertEqual(results[0]["report_id"], "R1")
        with AIStore(self.database) as store:
            self.assertTrue(store.report_coverage()["complete"])

    async def test_triage_pipeline_persists_summary_for_agent(self):
        client = FakeStructuredClient({"decisions": [{"cluster_id": "c1", "decision": "investigate", "reason": "Shared signals"}]})
        await triage_groups(AIService(client), self.database, [{"cluster_id": "c1", "app_ids": ["A", "B"]}])
        result = GraphTools(self.database).get_cluster("c1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["triage"]["decision"], "investigate")
        self.assertEqual(result["data"]["app_ids"], ["A", "B"])

    def test_obfuscated_indicators_and_shortener_paths_keep_identity(self):
        self.assertEqual(canonical_indicator(Indicator(kind="bank_account", raw="00o1 2345", bank="ACB")), "account:bank:ACB:00012345")
        self.assertNotEqual(canonical_indicator(Indicator(kind="url", raw="bit.ly/path-a")),
                            canonical_indicator(Indicator(kind="url", raw="bit.ly/path-b")))
        self.assertEqual(canonical_indicator(Indicator(kind="url", raw="https://WWW.Example.com/path")), "domain:example.com")

    def test_literal_context_span_can_contain_bank_label_but_not_two_numbers(self):
        self.assertEqual(canonical_indicator(Indicator(kind="bank_account", raw="STB 5682830100650", bank="STB")),
                         "account:bank:STB:5682830100650")
        with self.assertRaises(ValueError):
            canonical_indicator(Indicator(kind="bank_account", raw="0012345678 va 0098765432", bank="ACB"))

    def test_report_enrichment_is_idempotent_and_evidence_is_auditable(self):
        analysis = ReportAnalysis.model_validate(report_output())
        with AIStore(self.database) as store:
            text = json.loads(store.connection.execute("SELECT payload FROM scam_reports WHERE id='R1'").fetchone()[0])["raw_text"]
            store.persist_report("R1", text, analysis)
            store.persist_report("R1", text, analysis)
            page = store.reports_for_indicator("phone:0987654321")
            self.assertEqual(page["total_reports"], 1)
            edge_id = page["edges"][0]["id"]
            self.assertEqual(store.source_record(edge_id)["table"], "ai_report_analysis")
        tools = GraphTools(self.database)
        result = tools.reports_mentioning("phone:0987654321")
        self.assertEqual(result["data"]["total_reports"], 1)
        self.assertEqual(result["data"]["reports"][0]["reporter_app_ids"], ["A"])
        self.assertEqual(tools.get_application("A")["data"]["victim_self_report_count"], 1)
        self.assertNotIn("0987654321", json.dumps(result))
        self.assertEqual(tools.get_evidence(edge_id)["data"]["record"]["verdict"], "scam")

    def test_report_enrichment_refuses_mismatched_source(self):
        with AIStore(self.database) as store:
            with self.assertRaises(ValueError):
                store.persist_report("R1", "different input", ReportAnalysis.model_validate(report_output()))
            self.assertIsNone(store.ai_record("ai_report_analysis", "R1"))

    def test_rebuilding_graph_clears_stale_ai_annotations(self):
        pair = self.pair()
        with AIStore(self.database) as store:
            store.persist_entities([pair], [EntityDecision(pair_id="p1", decision="same", confidence=0.9, reason="Matching")])
        build_graph(self.directory, self.database, replace=True)
        with AIStore(self.database) as store:
            self.assertIsNone(store.ai_record("ai_entity_decisions", "p1"))
            self.assertEqual(store.entity_details("app:A")["app_ids"], ["A"])

    def test_identity_merge_does_not_destroy_original_nodes(self):
        pair = self.pair()
        decision = EntityDecision(pair_id="p1", decision="same", confidence=0.9, reason="Matching supplied attributes")
        with AIStore(self.database) as store:
            store.persist_entities([pair], [decision])
            self.assertEqual(store.entity_details("app:A")["app_ids"], ["A", "B"])
            self.assertEqual(store.node("person:012345678901")["kind"], "Person")
        result = GraphTools(self.database).entity_info("app:A")
        self.assertEqual(result["data"]["app_ids"], ["A", "B"])

    def test_conflicting_identity_decision_rolls_back(self):
        pair = self.pair()
        same = EntityDecision(pair_id="p1", decision="same", confidence=0.9, reason="Matching attributes")
        other_pair = pair.model_copy(update={"pair_id": "p2"})
        different = EntityDecision(pair_id="p2", decision="different", confidence=0.9, reason="Different people")
        with AIStore(self.database) as store:
            store.persist_entities([pair], [same])
            with self.assertRaises(ValueError):
                store.persist_entities([other_pair], [different])
            self.assertIsNone(store.ai_record("ai_entity_decisions", "p2"))
            self.assertEqual(store.entity_details("app:A")["app_ids"], ["A", "B"])

    def test_household_is_not_merged_as_same_person(self):
        pair = self.pair()
        decision = EntityDecision(pair_id="p1", decision="same_household", confidence=0.9, reason="Shared household")
        with AIStore(self.database) as store:
            store.persist_entities([pair], [decision])
            self.assertEqual(store.entity_details("app:A")["app_ids"], ["A"])
            self.assertEqual(len(store.related_edges("app:A", edge_type="HOUSEHOLD_CANDIDATE")["edges"]), 1)

    def test_missing_analyses_are_not_reported_as_complete(self):
        tools = GraphTools(self.database)
        result = tools.reports_mentioning("account:bank:ACB:001234567890")
        self.assertTrue(result["ok"])
        self.assertFalse(result["data"]["analysis_available"])
        self.assertFalse(result["data"]["analysis_coverage"]["complete"])

    def test_new_investigation_tools_are_paginated_and_masked(self):
        tools = GraphTools(self.database)
        account = tools.money_flow("A")["data"]["transfers"][0]["target"]
        result = tools.account_senders(account, limit=1)
        self.assertTrue(result["data"]["truncated"])
        self.assertEqual(result["data"]["app_ids"], ["A"])
        self.assertEqual(tools.timeline(["A", "B"])["data"]["app_ids"], ["A", "B"])
        profile = tools.tech_profile(["A", "B"])
        self.assertTrue(profile["ok"])
        self.assertIsNone(profile["data"]["suspicious_ekyc_ratio"])
        self.assertNotIn("0900000001", json.dumps(profile))

    def test_entity_blocking_only_uses_input_records_and_is_bounded(self):
        with AIStore(self.database) as store:
            pairs = entity_candidates(store.records("applications"), limit=1)
        self.assertEqual(len(pairs), 1)
        self.assertNotIn("cccd", pairs[0].left.model_dump())
        self.assertNotIn("shared", pairs[0].left.device_token)

    def test_evaluation_selection_and_denominators_are_explicit(self):
        truth = {"reports": {"a": {"label": "scam_injection"}, "b": {"label": "legit"}, "c": {"label": "scam_other"}}}
        self.assertEqual(select_reports(truth, 2), ["a", "b"])
        self.assertEqual(accuracy([{"expected": "scam", "correct": True}, {"expected": "safe", "correct": False}])["accuracy"], 0.5)
        self.assertIsNone(accuracy([])["accuracy"])

    async def test_evaluation_rejects_missing_source_ids_before_calling_model(self):
        truth = {"reports": {"missing-report": {"label": "scam"}}, "fraud_rings": [], "victims": [], "benign_groups": []}
        (self.directory / "ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
        client = FakeStructuredClient(report_output())
        with self.assertRaises(ValueError):
            await evaluate(AIService(client), client, self.database, self.directory,
                           report_limit=1, investigation_limit=0)
        self.assertEqual(client.calls, 0)


class AIHTTPTests(unittest.TestCase):
    def test_report_endpoint_and_validation(self):
        with TestClient(create_app(tool_llm_client=FakeStructuredClient(report_output()))) as client:
            self.assertEqual(client.post("/api/ai/shield/analyze", json={"text": "Call 0987654321"}).status_code, 200)
            self.assertEqual(client.post("/api/ai/shield/analyze", json={"text": "x" * 2001}).status_code, 422)
            self.assertEqual(client.post("/api/ai/shield/analyze", json={"text": "x", "label": "scam"}).status_code, 422)

    def test_missing_provider_and_invalid_output_do_not_become_safe_verdict(self):
        with TestClient(create_app(tool_llm_client=UnconfiguredToolLLMClient())) as client:
            self.assertEqual(client.post("/api/ai/shield/analyze", json={"text": "test"}).status_code, 503)
        with TestClient(create_app(tool_llm_client=FakeStructuredClient(report_output(confidence=99)))) as client:
            response = client.post("/api/ai/shield/analyze", json={"text": "test"})
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("safe", response.text)

    def test_other_ai_endpoints_have_explicit_contracts(self):
        app = create_app(tool_llm_client=UnconfiguredToolLLMClient())
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/ai/entities/resolve", json={"pairs": []}).status_code, 422)
            self.assertEqual(client.post("/api/ai/triage", json={"clusters": []}).status_code, 422)
            self.assertEqual(client.post("/api/ai/transfer/check", json={"loan_amount": 0}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
