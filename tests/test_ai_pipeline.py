import csv
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import test_backend_integration as fixtures
from app.ai.evaluation.pipeline import score_pipeline
from app.ai.pipeline.runner import PipelineBusyError, PipelineService
from app.ai.pipeline.schemas import PipelineRequest
from app.graph.ai_store import AIStore
from app.main import create_app
from app.services.tool_llm import ModelTurn, ToolCall


class PipelineClient:
    model = "pipeline-unit-test"

    def __init__(self, *, skip=False, bad_report=False):
        self.skip, self.bad_report = skip, bad_report
        self.model = "pipeline-unit-" + ("skip" if skip else "investigate") + ("-bad-report" if bad_report else "")
        self.calls, self.inputs = [], []

    def ensure_ready(self):
        pass

    async def complete(self, messages, definitions):
        name = definitions[0]["name"]
        if len(definitions) == 1 and name == "report_verdict":
            output = {"verdict": "scam", "confidence": .8, "reporter_is_victim": True,
                      "indicators": [{"kind": "bank_account", "raw": "999999999999" if self.bad_report else "001234567890", "bank": "ACB"}],
                      "reasons": ["Victim describes an advance-fee request"], "advice": "Verify recipient", "tactics": ["advance_fee"]}
        elif len(definitions) == 1 and name == "er_decisions":
            payload = json.loads(messages[1].content)
            output = {"decisions": [{"pair_id": p["pair_id"], "decision": "same_household", "confidence": .7,
                                     "reason": "Shared household needs separate identities"} for p in payload["pairs"]]}
        elif len(definitions) == 1 and name == "triage":
            payload = json.loads(messages[1].content)
            output = {"decisions": [{"cluster_id": c["cluster_id"], "decision": "skip" if self.skip else "investigate",
                                     "suspected_type": None, "reason": "Review available report and graph evidence"} for c in payload["clusters"]]}
        else:
            previous = [json.loads(m.content) for m in messages if m.role == "tool"]
            if not previous:
                name, output = "cluster_money_flow", {"cluster_id": "C1"}
            elif len(previous) == 1:
                name, output = "get_application", {"app_id": "A"}
            else:
                name, output = "submit_case", {"verdict": "victims", "confidence": .7,
                    "members": [], "victims": ["A"], "evidence": [{"claim": "Indexed victim report", "source": previous[-1]["tool_call_id"]}],
                    "benign_explanation": "Considered an ordinary transfer; an indexed self-report calls for support", "actions": ["Verify with customer"]}
                output["cluster_assessment"] = {"level": "suspicious", "reason": "Report-linked transfer needs review",
                    "evidence": [{"claim": "Cluster flow and reports observed", "source": previous[0]["tool_call_id"]}],
                    "limitations": ["Only part of the reports are indexed"]}
                output["application_assessments"] = [{"app_id": "A", "role": "possible_victim", "reason": "Indexed self-report",
                    "evidence": [{"claim": "Self-report belongs to A", "source": previous[-1]["tool_call_id"]}]}]
        self.inputs.extend(m.content for m in messages if m.role == "user")
        self.calls.append(name)
        return ModelTurn(tool_calls=[ToolCall(id=f"call-{len(self.calls)}", name=name, arguments=output)])


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = fixtures.BackendIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.database.parent / "pipeline-runs"
        with sqlite3.connect(self.fixture.database) as db:
            db.execute("ALTER TABLE alerts ADD COLUMN latest DEFAULT 1")
            db.execute("ALTER TABLE alerts ADD COLUMN priority DEFAULT 10")
            db.execute("ALTER TABLE apps ADD COLUMN signals DEFAULT '[\"mock-signal\"]'")
            db.execute("UPDATE reports SET raw_text='I was tricked into sending money to ACB 001234567890' WHERE report_id='R1'")
            db.row_factory = sqlite3.Row
            row = dict(db.execute("SELECT * FROM apps").fetchone())
            row.update(app_id="B", phone="0900000002", cccd="012345678902")
            db.execute("INSERT INTO apps VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))
            db.execute("UPDATE alerts SET app_ids='[\"A\",\"B\"]'")

    def config(self, **changes):
        return PipelineRequest(**{"report_limit": 1, "cluster_limit": 1, "investigation_limit": 1,
                                  "entity_pair_limit": 2, **changes})

    async def test_complete_pipeline_uses_ai_enrichment_and_keeps_backend_unchanged(self):
        client = PipelineClient()
        before = hashlib.sha256(self.fixture.database.read_bytes()).hexdigest()
        runner = PipelineService(client, self.fixture.database, self.root)
        result = await runner.run(self.config())
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(client.calls, ["report_verdict", "er_decisions", "triage", "cluster_money_flow", "get_application", "submit_case"])
        self.assertEqual(result["model_calls"], len(client.calls))
        self.assertEqual(result["clusters"][0]["case"]["verdict"], "victims")
        self.assertEqual(result["stages"]["reports"]["result"]["coverage"]["indexed"], 1)
        self.assertEqual(result["stages"]["reports"]["result"]["coverage"]["total"], 2)
        self.assertEqual(runner.read(result["run_id"]), result)
        trace = runner.read_trace(result["run_id"], "C1")
        self.assertEqual(trace["case"]["cluster_assessment"]["level"], "suspicious")
        self.assertEqual(trace["steps"][0]["name"], "cluster_money_flow")
        with self.assertRaises(FileNotFoundError):
            runner.read_trace(result["run_id"], "unknown")
        manifest = self.root / result["run_id"] / "result.json"
        unsafe = json.loads(manifest.read_text(encoding="utf-8"))
        unsafe["clusters"][0]["trace_file"] = "../outside.json"
        manifest.write_text(json.dumps(unsafe), encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            runner.read_trace(result["run_id"], "C1")
        manifest.write_text(json.dumps(result), encoding="utf-8")
        directory = self.root / result["run_id"]
        with (directory / "source" / "scam_reports.csv").open(encoding="utf-8-sig") as f:
            self.assertNotIn("analysis", next(csv.reader(f)))
        with (directory / "source" / "applications.csv").open(encoding="utf-8-sig") as f:
            self.assertNotIn("signals", next(csv.reader(f)))
        self.assertEqual(hashlib.sha256(self.fixture.database.read_bytes()).hexdigest(), before)
        self.assertNotIn("mock-signal", " ".join(client.inputs))
        with AIStore(directory / "graph.db", read_only=True) as store:
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM edges WHERE kind='MENTIONS'").fetchone()[0], 1)
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM ai_entity_decisions").fetchone()[0], 1)

    async def test_skip_and_budget_deferral_are_not_benign_verdicts(self):
        skipped = await PipelineService(PipelineClient(skip=True), self.fixture.database, self.root).run(self.config())
        self.assertEqual(skipped["clusters"][0]["status"], "skipped_by_triage")
        self.assertNotIn("case", skipped["clusters"][0])
        deferred = await PipelineService(PipelineClient(), self.fixture.database, self.root).run(self.config(investigation_limit=0))
        self.assertEqual(deferred["status"], "partial")
        self.assertEqual(deferred["clusters"][0]["status"], "deferred_by_limit")
        self.assertNotIn("case", deferred["clusters"][0])

    async def test_hallucinated_report_does_not_create_edges_or_fake_full_coverage(self):
        result = await PipelineService(PipelineClient(bad_report=True), self.fixture.database, self.root).run(self.config())
        self.assertEqual(result["status"], "partial")
        reports = result["stages"]["reports"]["result"]
        self.assertEqual(reports["coverage"]["indexed"], 0)
        self.assertEqual(len(reports["errors"]), 1)
        with AIStore(self.root / result["run_id"] / "graph.db", read_only=True) as store:
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM edges WHERE kind='MENTIONS'").fetchone()[0], 0)

    async def test_bad_candidate_selection_stops_before_calling_model_and_persists_failure(self):
        client = PipelineClient()
        runner = PipelineService(client, self.fixture.database, self.root)
        result = await runner.run(self.config(cluster_ids=["unknown"]))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stages"]["snapshot"]["status"], "failed")
        self.assertEqual(client.calls, [])
        self.assertEqual(runner.read(result["run_id"])["status"], "failed")

    async def test_one_active_run_and_no_path_traversal(self):
        runner = PipelineService(PipelineClient(), self.fixture.database, self.root)
        async with runner.lock:
            with self.assertRaises(PipelineBusyError):
                await runner.run(self.config())
        with self.assertRaises(FileNotFoundError):
            runner.read("../not-a-run")
        self.assertFalse(self.root.exists())

    async def test_scoring_is_post_run_and_counts_abstention_and_wrong_role(self):
        result = await PipelineService(PipelineClient(), self.fixture.database, self.root).run(self.config())
        truth = self.fixture.database.parent / "ground_truth.json"
        truth.write_text(json.dumps({"fraud_rings": [], "victims": [{"app_ids": ["A"]}]}), encoding="utf-8")
        score = score_pipeline(result, truth)
        self.assertEqual(score["victims_identified"], 1)
        self.assertEqual(score["false_offender_flags"], 0)
        self.assertEqual(score["selected_applications"], 2)
        self.assertEqual(score["inconclusive_rate"], 0)
        self.assertEqual(score["cluster_assessment_levels"], {"suspicious": 1})
        self.assertEqual(score["application_assessments_count"], 1)
        self.assertEqual(score["applications_not_assessed"], 1)
        self.assertEqual(score["possible_victims_matching_synthetic_victims"], 1)

    async def test_api_runs_and_loads_result_with_fixed_server_side_paths(self):
        app = create_app(tool_llm_client=PipelineClient(), backend_database=self.fixture.database,
                         service_api_key="", web_password="", pipeline_directory=self.root)
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/ai/pipeline/run", json={"database": "arbitrary.db"}).status_code, 422)
            response = client.post("/api/ai/pipeline/run", json=self.config().model_dump())
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "completed")
            trace_url = "/api/ai/pipeline/runs/" + response.json()["run_id"] + "/traces/C1"
            self.assertEqual(client.get(trace_url).json()["steps"][0]["name"], "cluster_money_flow")
            self.assertEqual(client.get(trace_url.replace("C1", "unknown")).status_code, 404)
            for _ in range(3):
                self.assertEqual(client.get("/api/ai/pipeline/runs/" + response.json()["run_id"]).status_code, 200)
            self.assertEqual(client.get("/api/ai/pipeline/runs/" + "0" * 32).status_code, 404)

    async def test_pipeline_api_requires_web_auth_when_password_enabled(self):
        app = create_app(tool_llm_client=PipelineClient(), backend_database=self.fixture.database,
                         service_api_key="", web_password="test-password", pipeline_directory=self.root)
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/ai/pipeline/run", json={}).status_code, 401)
            self.assertEqual(client.get("/api/ai/pipeline/runs/" + "0" * 32).status_code, 401)
            self.assertEqual(client.get("/api/ai/pipeline/runs/" + "0" * 32 + "/traces/C1").status_code, 401)
        self.assertFalse(self.root.exists())
