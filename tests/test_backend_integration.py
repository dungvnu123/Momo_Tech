import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.agent_tools import BackendAgentTools
from app.backend.store import Tools
from app.main import create_app
from app.services.tool_llm import ModelTurn, ToolCall
from test_investigation import ScriptedClient, submission, detailed_submission, turn


class BackendIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "backend.db"
        db = sqlite3.connect(self.database)
        row = dict(app_id="A", phone="0900000001", full_name="PRIVATE NAME", dob="1990-01-01",
                   address="PRIVATE ADDRESS", cccd="012345678901", amount="1000000", device_id="PRIVATE DEVICE",
                   applied_at="2026-11-01T08:00:00", disbursed_at="2026-11-01T08:10:00", ip_type="mobile",
                   sim_age_days="100", is_emulator="False", is_rooted_or_hooked="False", device_first_seen_hours="100",
                   fill_time_sec="180", ref1_phone="0900000002", ref2_phone="0900000003")
        db.execute("CREATE TABLE apps (" + ",".join(row) + ")")
        db.execute("INSERT INTO apps VALUES (" + ",".join("?" for _ in row) + ")", list(row.values()))
        db.execute("CREATE TABLE transfers (transfer_id,from_wallet,to_id,to_name,to_bank,to_type,amount,created_at,"
                   "recipient_in_contacts,contact_saved_minutes_ago,prior_transfers_to_recipient,simo_flag,to_wallet_age_days,note)")
        for identifier, timestamp in [("CK00001", "2026-11-01T08:20:00"), ("CK00002", "2026-11-03T08:20:00")]:
            db.execute("INSERT INTO transfers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (identifier, row["phone"], "001234567890", "PRIVATE RECIPIENT", "ACB", "bank", "900000",
                        timestamp, "False", "", "0", "False", "", "PRIVATE NOTE"))
        db.execute("CREATE TABLE reports (report_id,reported_at,reporter_phone,channel,raw_text,analysis)")
        for identifier, timestamp in [("R1", "2026-11-01T08:25:00"), ("R2", "2026-11-03T08:25:00")]:
            db.execute("INSERT INTO reports VALUES (?,?,?,?,?,?)", (identifier, timestamp, row["phone"], "app", "PRIVATE REPORT",
                       json.dumps({"verdict": "scam", "reporter_is_victim": True,
                                   "indicators": {"accounts": ["001234567890"], "phones": []}, "mode": "mock"})))
        db.execute("CREATE TABLE alerts (alert_id,cid,ts,app_ids,signals,n_pending,verdict,case_conf)")
        db.execute("INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?)", ("AL1", "C1", "2026-11-01T09:00:00", '["A"]', '[]', 0, None, None))
        db.execute("CREATE TABLE cases (alert_id PRIMARY KEY,cid,verdict,members,victims,body)")
        db.execute("CREATE TABLE meta (k,v)")
        db.execute("INSERT INTO meta VALUES ('last_day','\"2026-11-25\"')")
        db.commit()
        db.close()

    def client(self, model, **options):
        client = TestClient(create_app(tool_llm_client=model, backend_database=self.database,
                                      service_api_key=options.get("service_api_key", "")))
        return self.enterContext(client)

    def tools(self):
        store = Tools(self.database)
        self.addCleanup(store.db.close)
        return BackendAgentTools(store, store.alert("AL1"))

    def test_snapshot_excludes_future_records_and_raw_identifiers(self):
        tools = self.tools()
        flow = tools.call("money_flow", {})
        self.assertTrue(flow["ok"])
        self.assertEqual([t["transfer_id"] for t in flow["data"]["transfers"]], ["CK00001"])
        self.assertEqual([r["report_id"] for r in tools.call("reports_mentioning", {})["data"]["reports"]], ["R1"])
        application = tools.call("get_application", {"app_id": "A"})
        self.assertEqual(application["data"]["victim_self_report_count"], 1)
        self.assertTrue(tools.call("get_application", {"app_id": "app:A"})["ok"])
        serialized = json.dumps([flow, application, tools.call("reports_mentioning", {})])
        for private in ("0900000001", "001234567890", "PRIVATE", "012345678901", "CK00002", "R2"):
            self.assertNotIn(private, serialized)
        recipient = flow["data"]["recipients"][0]
        self.assertEqual(len(tools.call("account_senders", {"node_id": recipient})["data"]["senders"]), 1)

    def test_scope_and_argument_validation(self):
        tools = self.tools()
        for name, arguments in [("get_application", {"app_id": "UNKNOWN"}), ("tech_profile", {"app_ids": ["UNKNOWN"]}),
                                ("get_cluster", {"cluster_id": "OTHER"}), ("account_senders", {"node_id": "001234567890"}),
                                ("get_cluster", {"sql": "SELECT * FROM apps"})]:
            self.assertFalse(tools.call(name, arguments)["ok"])

    def test_shield_uses_real_service_and_preserves_frontend_contract(self):
        model = ScriptedClient(turn("shield", "report_verdict", {
            "verdict": "scam", "confidence": 0.9, "reporter_is_victim": False, "tactics": [],
            "indicators": [{"kind": "bank_account", "raw": "001234567890", "bank": "ACB"}],
            "reasons": ["Requests money"], "advice": "Do not transfer"}))
        response = self.client(model).post("/api/shield/analyze", json={"text": "ACB 001234567890"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["indicators"]["accounts"], ["001234567890"])
        self.assertEqual(response.json()["times_reported"], 2)
        self.assertEqual(model.offered_tools[0], ["report_verdict"])

    def test_shield_samples_load_without_calling_the_model(self):
        model = ScriptedClient()
        response = self.client(model).get("/api/shield/samples")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["text"], "PRIVATE REPORT")
        self.assertTrue(response.json()[0]["label"])
        self.assertEqual(model.history, [])

    def test_transfer_uses_real_service_and_maps_context(self):
        model = ScriptedClient(turn("transfer", "transfer_verdict", {
            "decision": "warn", "confidence": 0.8, "reasons": ["New recipient"], "advice": "Check recipient"}))
        response = self.client(model).post("/api/transfer/check", json={"transfer_id": "CK00001"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["message_for_customer"], "Check recipient")
        payload = json.loads(model.history[0][1].content)
        self.assertEqual(payload["transfer_amount"], 900000)
        self.assertNotIn("PRIVATE", model.history[0][1].content)

    def test_sse_investigation_uses_base_agent_and_persists_case(self):
        model = ScriptedClient(turn("read-1", "cluster_money_flow", {}), turn("finish", "submit_case", detailed_submission(
            verdict="victims", victims=["A"], actions=["Support customer"])))
        client = self.client(model)
        response = client.get("/api/alerts/AL1/investigate")
        self.assertEqual(response.status_code, 200, response.text)
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertTrue(any(e["type"] == "step" for e in events))
        self.assertEqual(events[-1]["case"]["verdict"], "victims")
        self.assertEqual(events[-1]["case"]["status"], "completed")
        stored = client.app.state.backend_tools.q("SELECT body FROM cases")[0]
        self.assertEqual(json.loads(stored["body"])["victims"], ["A"])
        self.assertEqual(len(json.loads(stored["body"])["tool_steps"]), 2)
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/flows/").status_code, 200)
        self.assertIn("/api/ai/shield/analyze", client.get("/openapi.json").json()["paths"])

    def test_invalid_or_failed_run_does_not_overwrite_previous_case(self):
        model = ScriptedClient(turn("read", "get_cluster", {}), ModelTurn())
        client = self.client(model)
        store = client.app.state.backend_tools
        store.db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?)", ("AL1", "C1", "benign", '[]', '[]', '{"mode":"mock"}'))
        store.db.commit()
        response = client.get("/api/alerts/AL1/investigate")
        self.assertIn('"inconclusive"', response.text)
        self.assertEqual(store.q("SELECT verdict FROM cases")[0]["verdict"], "benign")

    def test_service_key_protects_backend_routes(self):
        client = self.client(ScriptedClient(), service_api_key="test-service-key")
        self.assertEqual(client.get("/api/overview").status_code, 401)
        self.assertEqual(client.get("/api/overview", headers={"X-API-Key": "test-service-key"}).status_code, 200)
        self.assertEqual(client.get("/health").status_code, 200)
