import asyncio
import json
import os
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

import test_backend_integration as fixtures
from app.ai.service import AIService
from app.ai.realtime.service import RealtimeService
from app.backend.agent_tools import BackendAgentTools
from app.backend.events import ensure_schema, publish
from app.ai.realtime import jobs
from app.ai.realtime.alerts import snapshot
from app.backend.store import Tools
from app.graph.ai_store import AIStore
from app.graph.ingestion import ingest_event
from app.ai.shield.schemas import ReportAnalysis
from app.backend.report_view import report_view
from app.backend.events.knowledge import related_case_count, recipient_reports
from app.main import create_app
from app.security import hash_pin
from app.services.tool_llm import ModelTurn, ToolCall, UnconfiguredToolLLMClient


class RealtimeClient:
    def __init__(self, *, skip=False):
        self.calls, self.skip = [], skip

    def ensure_ready(self):
        pass

    async def complete(self, messages, definitions):
        reads = [json.loads(m.content) for m in messages if m.role == "tool"]
        names = {d["name"] for d in definitions}
        if "triage" in names:
            payload = json.loads(next(m.content for m in messages if m.role == "user"))
            name, args = (
                "triage",
                {
                    "decisions": [
                        {
                            "cluster_id": c["cluster_id"],
                            "decision": "skip" if self.skip else "investigate",
                            "reason": "Review source-linked new activity",
                        }
                        for c in payload["clusters"]
                    ]
                },
            )
        elif not reads:
            name, args = "get_cluster", {}
        elif len(reads) == 1:
            name, args = "cluster_money_flow", {}
        elif reads[0]["data"].get("triggering_transfer_id") and len(reads) == 2:
            name, args = "get_transfer", {"transfer_id": reads[0]["data"]["triggering_transfer_id"]}
        else:
            scope = reads[1]
            proof = {
                "claim": "The scoped records require verification",
                "source": scope["tool_call_id"],
            }
            args = {
                "verdict": "inconclusive",
                "confidence": 0.4,
                "members": [],
                "victims": [],
                "summary": "New transfer activity needs human verification",
                "evidence": [proof],
                "benign_explanation": "An ordinary payment remains possible",
                "missing_information": ["Ask the customer"],
                "actions": ["Verify recipient and customer intent"],
                "cluster_assessment": {
                    "level": "suspicious",
                    "reason": "New source-linked activity",
                    "evidence": [proof],
                    "limitations": ["Reports and roles remain unverified"],
                },
                "application_assessments": [
                    {
                        "app_id": a["app_id"],
                        "role": "undetermined",
                        "reason": "Observed loan snapshot",
                        "evidence": [{**proof, "record_ids": [a["record_id"]]}],
                        "missing_information": ["Verify intent"],
                    }
                    for a in scope["data"]["application_summaries"]
                ],
            }
            focused = reads[0]["data"].get("triggering_transfer_id")
            if focused:
                args["transaction_assessments"] = [
                    {
                        "transfer_id": focused,
                        "recommendation": "review",
                        "reason": "Check actual transfer state",
                        "evidence": [
                            {
                                "claim": "Exact triggering transaction",
                                "source": reads[2]["tool_call_id"],
                            }
                        ],
                    }
                ]
            name = "submit_case"
        self.calls.append(name)
        return ModelTurn(
            tool_calls=[ToolCall(id=f"live-call-{len(self.calls)}", name=name, arguments=args)]
        )


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BackendIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = Tools(self.fixture.database)
        self.addCleanup(self.store.db.close)
        for name, kind in {
            "day": "TEXT",
            "kind": "TEXT",
            "transfer_id": "TEXT",
            "title": "TEXT",
            "reason": "TEXT",
            "severity": "TEXT",
            "priority": "REAL",
            "confidence": "REAL",
            "size": "INT",
            "n_reports": "INT",
            "suspected_type": "TEXT",
            "latest": "BOOLEAN DEFAULT TRUE",
        }.items():
            self.store.run(f"ALTER TABLE alerts ADD COLUMN {name} {kind}")
        self.store.db.executescript("""
            CREATE TABLE khach_accounts(phone TEXT PRIMARY KEY,app_id TEXT,display_name TEXT,pin_salt BYTEA,pin_hash BYTEA,balance BIGINT);
            CREATE TABLE khach_loans(loan_id SERIAL PRIMARY KEY,phone TEXT,amount BIGINT,disbursed_at TEXT);
            CREATE TABLE khach_transfers(tx_id SERIAL PRIMARY KEY,phone TEXT,ts TEXT,to_type TEXT,to_id TEXT,to_bank TEXT,to_name TEXT,
                amount BIGINT,note TEXT,decision TEXT,reasons TEXT,status TEXT);
            CREATE TABLE khach_contacts(phone TEXT,contact_phone TEXT,name TEXT,saved_at TEXT,PRIMARY KEY(phone,contact_phone));
            CREATE TABLE khach_inbox(msg_id SERIAL PRIMARY KEY,phone TEXT,ts TEXT,sender TEXT,body TEXT,kind TEXT,is_read BOOLEAN,reported_verdict TEXT);
            CREATE TABLE simo_list(to_id TEXT PRIMARY KEY);
            CREATE TABLE ring_accounts(to_id TEXT,cid TEXT,verdict TEXT,n_senders INT);
        """)
        ensure_schema(self.store)
        salt = b"fixed-test-salt!"
        self.store.run(
            "INSERT INTO khach_accounts VALUES (?,?,?,?,?,?)",
            "0900000001",
            "A",
            "PRIVATE NAME",
            salt,
            hash_pin("123456", salt),
            10_000_000,
        )
        self.graph = self.fixture.database.parent / "live-graph.db"
        self.client = RealtimeClient()
        self.service = RealtimeService(
            self.fixture.database,
            self.graph,
            AIService(self.client),
            self.client,
            max_per_minute=100,
        )

    def loan(self, amount=2_000_000, at="2026-11-01T09:01:00"):
        return self.store.q(
            "INSERT INTO khach_loans(phone,app_id,amount,disbursed_at) VALUES ('0900000001','A',?,?) RETURNING loan_id",
            amount,
            at,
        )[0]["loan_id"]

    def transfer(self, loan_id, *, status="held", at="2026-11-01T09:02:00", amount=500_000):
        context = json.dumps(
            {
                "loan_id": loan_id,
                "loan_amount": 2_000_000,
                "minutes_after_disbursal": 1,
                "simo_flag": False,
                "recipient_in_contacts": False,
                "prior_transfers_to_recipient": 0,
            }
        )
        tx = self.store.q(
            "INSERT INTO khach_transfers(phone,ts,to_type,to_id,to_bank,to_name,amount,note,decision,reasons,status,app_id,loan_id,context) "
            "VALUES ('0900000001',?,'bank','001234567890','ACB','PRIVATE RECIPIENT',?,'',?,'[]',?,'A',?,?) RETURNING tx_id",
            at,
            amount,
            "hold" if status == "held" else "allow",
            status,
            loan_id,
            context,
        )[0]["tx_id"]
        return "KT" + str(tx)

    def event(self, transfer_id, *, simulated=False):
        publish(
            self.store, "transfer", transfer_id, "A", "2026-11-01T09:02:00", simulated=simulated
        )

    def test_exact_loan_and_held_attempt_do_not_inflate_completed_outflow(self):
        lid = self.loan()
        done = self.transfer(lid, status="done", at="2026-11-01T09:01:30", amount=900_000)
        held = self.transfer(lid)
        self.loan(7_000_000, at="2026-11-01T09:01:45")
        alert = self.store.alert("AL1")
        alert.update(
            ts="2026-11-01T09:02:00",
            kind="transfer",
            transfer_id=held,
            context={"loan_ids": {"A": lid}},
        )
        tools = BackendAgentTools(self.store, alert)
        data = tools.call("cluster_money_flow", {})["data"]
        self.assertEqual(data["totals"]["loan_amount"], 2_000_000)
        self.assertEqual(data["totals"]["transfer_amount"], 900_000)
        self.assertEqual(data["totals"]["held_amount"], 500_000)
        self.assertEqual({r["transfer_id"] for r in data["transfers"]}, {done, held})
        self.assertEqual(
            tools.call("get_transfer", {"transfer_id": held})["data"]["transfer"]["source"][
                "table"
            ],
            "khach_transfers",
        )
        for private in ("0900000001", "001234567890", "PRIVATE"):
            self.assertNotIn(private, json.dumps(data))

    def test_worker_persists_case_graph_and_unverified_links_and_replay_is_idempotent(self):
        tx = self.transfer(self.loan())
        self.event(tx)
        self.event(tx)
        self.assertTrue(asyncio.run(self.service.process_one()))
        event = self.store.q("SELECT * FROM ai_events")[0]
        self.assertEqual(event["status"], "completed", event)
        result = json.loads(event["result"])
        case = json.loads(
            self.store.q("SELECT body FROM cases WHERE alert_id=?", result["alert_id"])[0]["body"]
        )
        self.assertEqual(case["status"], "completed")
        self.assertEqual(case["transaction_assessments"][0]["transfer_id"], tx)
        self.assertEqual(case["tool_steps"][1]["result"]["data"]["totals"]["transfer_amount"], 0)
        self.assertEqual(
            self.store.q("SELECT verification_status FROM ai_case_recipients")[0][
                "verification_status"
            ],
            "unverified",
        )
        with AIStore(self.graph, read_only=True) as graph:
            self.assertEqual(
                graph.connection.execute(
                    "SELECT COUNT(*) FROM edges WHERE kind='TRANSFER_ATTEMPT'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(graph.money_summary("A")["total_amount"], 0)
        calls = len(self.client.calls)
        self.store.run("UPDATE ai_events SET status='retry',available_at=now()")
        self.assertTrue(asyncio.run(self.service.process_one()))
        self.assertEqual(len(self.client.calls), calls)
        self.assertFalse(asyncio.run(self.service.process_one()))

    def test_simulation_updates_graph_without_calling_model(self):
        self.event(self.transfer(self.loan(), status="done"), simulated=True)
        asyncio.run(self.service.process_one())
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.store.q("SELECT status FROM ai_events")[0]["status"], "completed")

    def test_missing_model_keeps_job_pending_without_fabricated_case(self):
        self.event(self.transfer(self.loan()))
        self.service.client = UnconfiguredToolLLMClient()
        asyncio.run(self.service.process_one())
        row = self.store.q("SELECT status,attempts FROM ai_events")[0]
        self.assertEqual(row, {"status": "waiting_for_model", "attempts": 0})
        self.assertEqual(self.store.q("SELECT COUNT(*) AS n FROM cases")[0]["n"], 0)

    def test_expired_final_lease_and_transaction_rollback_are_recoverable(self):
        with self.assertRaises(ValueError):
            with self.store.transaction():
                publish(self.store, "loan", "KL99", "A", "2026-11-01T09:00:00")
                raise ValueError("Rollback")
        self.assertEqual(self.store.q("SELECT COUNT(*) AS n FROM ai_events")[0]["n"], 0)
        self.event(self.transfer(self.loan()))
        self.store.run(
            "UPDATE ai_events SET status='running',attempts=3,lease_until=now()-interval '1 second'"
        )
        self.assertIsNone(jobs.claim(self.store))
        self.assertEqual(self.store.q("SELECT status FROM ai_events")[0]["status"], "failed")

    def test_same_second_future_events_do_not_leak_into_snapshot(self):
        lid = self.loan()
        publish(self.store, "loan", "KL" + str(lid), "A", "2026-11-01T09:01:00")
        first = self.transfer(lid)
        self.event(first)
        event = jobs.claim(self.store)
        # The loan event is first; use the following transfer event as the snapshot cursor.
        event = jobs.claim(self.store)
        later = self.transfer(lid)
        self.event(later)
        future_loan = self.loan(9_000_000, at="2026-11-01T09:02:00")
        publish(self.store, "loan", "KL" + str(future_loan), "A", "2026-11-01T09:02:00")
        alert = snapshot(self.store, event, ["A"])
        data = BackendAgentTools(self.store, alert).call("cluster_money_flow", {})["data"]
        self.assertEqual([t["transfer_id"] for t in data["transfers"]], [first])
        self.assertEqual(data["totals"]["loan_amount"], 2_000_000)

    def test_report_ingestion_preserves_bank_scope_quote_and_idempotency(self):
        text = "I was tricked into sending money to ACB 001234567890"
        analysis = ReportAnalysis(
            verdict="scam",
            confidence=0.8,
            reporter_is_victim=True,
            indicators=[{"kind": "bank_account", "raw": "001234567890", "bank": "ACB"}],
            reasons=["Customer describes a scam"],
            advice="Verify recipient",
        )
        source = {
            "report_id": "NEW1",
            "reported_at": "2026-11-01T09:02:00",
            "reporter_phone": "0900000001",
            "raw_text": text,
        }
        event = {"event_id": "report:NEW1", "kind": "report"}
        app = self.store.apps(["A"])[0]
        self.assertTrue(ingest_event(self.graph, event, app, source, analysis=analysis))
        self.assertFalse(ingest_event(self.graph, event, app, source, analysis=analysis))
        with AIStore(self.graph, read_only=True) as graph:
            self.assertEqual(
                graph.connection.execute(
                    "SELECT target FROM edges WHERE kind='MENTIONS'"
                ).fetchone()[0],
                "account:bank:ACB:001234567890",
            )
            self.assertEqual(
                graph.connection.execute(
                    "SELECT COUNT(*) FROM edges WHERE kind='MENTIONS'"
                ).fetchone()[0],
                1,
            )
        invalid = ReportAnalysis.model_validate(
            {
                **analysis.model_dump(),
                "indicators": [{"kind": "bank_account", "raw": "999999999999", "bank": "ACB"}],
            }
        )
        with self.assertRaises(ValueError):
            ingest_event(
                self.graph,
                {"event_id": "report:BAD", "kind": "report"},
                app,
                {**source, "report_id": "BAD"},
                analysis=invalid,
            )
        with AIStore(self.graph, read_only=True) as graph:
            self.assertIsNone(
                graph.connection.execute(
                    "SELECT 1 FROM ingested_events WHERE event_id='report:BAD'"
                ).fetchone()
            )

    def test_case_lookup_is_bank_scoped_and_does_not_promote_unverified_to_hold(self):
        tx = self.transfer(self.loan())
        self.event(tx)
        asyncio.run(self.service.process_one())
        self.assertEqual(related_case_count(self.store, "bank", "ACB", "001234567890"), 1)
        self.assertEqual(related_case_count(self.store, "bank", "VCB", "001234567890"), 0)

    def test_report_matching_does_not_join_other_bank_with_same_digits(self):
        typed = ReportAnalysis(
            verdict="scam",
            confidence=0.8,
            reporter_is_victim=False,
            indicators=[{"kind": "bank_account", "raw": "001234567890", "bank": "VCB"}],
            reasons=["Source report"],
            advice="Verify",
        )
        self.store.run("UPDATE reports SET analysis=?", json.dumps(report_view(typed)))
        tools = BackendAgentTools(self.store, self.store.alert("AL1"))
        transfer = tools.call("get_transfer", {"transfer_id": "CK00001"})["data"]["transfer"]
        self.assertEqual(transfer["reported_recipient_count"], 0)

    def test_background_worker_runs_and_stops_cleanly(self):
        self.event(self.transfer(self.loan()), simulated=True)

        async def run():
            self.service.start()
            try:
                async with asyncio.timeout(5):
                    while self.store.q("SELECT status FROM ai_events")[0]["status"] != "completed":
                        await asyncio.sleep(0.05)
            finally:
                await self.service.close()

        asyncio.run(run())
        self.assertTrue(self.service.task.done())

    def test_realtime_api_requires_risk_team_auth(self):
        with patch.dict(os.environ, {"AI_REALTIME_ENABLED": "0"}):
            application = create_app(
                tool_llm_client=self.client,
                backend_database=self.fixture.database,
                graph_database=self.graph,
                service_api_key="",
                web_password="private-test-password",
            )
            with TestClient(application) as client:
                self.assertEqual(client.get("/api/ai/realtime/events").status_code, 401)
                self.assertEqual(client.post("/api/ai/realtime/process").status_code, 401)

    def test_recipient_reports_separate_unknown_bank_and_safe_messages(self):
        self.assertEqual(
            recipient_reports(self.store, "bank", "ACB", "001234567890", "2026-11-01T09:00:00"),
            (0, 1),
        )
        typed = ReportAnalysis(
            verdict="scam",
            confidence=0.8,
            reporter_is_victim=False,
            indicators=[{"kind": "bank_account", "raw": "001234567890", "bank": "VCB"}],
            reasons=["Test source"],
            advice="Verify",
        )
        self.store.run("UPDATE reports SET analysis=?", json.dumps(report_view(typed)))
        self.assertEqual(
            recipient_reports(self.store, "bank", "ACB", "001234567890", "9999"), (0, 0)
        )
        self.assertEqual(
            recipient_reports(self.store, "bank", "VCB", "001234567890", "9999"), (2, 0)
        )
        safe = typed.model_copy(update={"verdict": "safe"})
        self.store.run("UPDATE reports SET analysis=?", json.dumps(report_view(safe)))
        self.assertEqual(
            recipient_reports(self.store, "bank", "VCB", "001234567890", "9999"), (0, 0)
        )

    def test_reporting_same_inbox_message_twice_creates_one_event(self):
        text = "Please send money to ACB 001234567890"
        msg = self.store.q(
            "INSERT INTO khach_inbox(phone,ts,body,kind) VALUES ('0900000001','2026-11-01T09:00:00',?,'unknown') RETURNING msg_id",
            text,
        )[0]["msg_id"]
        result = report_view(
            ReportAnalysis(
                verdict="scam",
                confidence=0.8,
                reporter_is_victim=False,
                indicators=[{"kind": "bank_account", "raw": "001234567890", "bank": "ACB"}],
                reasons=["Test source"],
                advice="Verify",
            )
        )
        with (
            patch.dict(os.environ, {"AI_REALTIME_ENABLED": "0"}),
            patch("app.khach.ai_report", new=AsyncMock(return_value=result)),
        ):
            application = create_app(
                tool_llm_client=self.client,
                backend_database=self.fixture.database,
                graph_database=self.graph,
                service_api_key="",
                web_password="",
            )
            with TestClient(application) as client:
                client.post("/api/khach/login", json={"phone": "0900000001", "pin": "123456"})
                for _ in range(2):
                    response = client.post(f"/api/khach/report/{msg}")
                    self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.store.q("SELECT COUNT(*) AS n FROM ai_events")[0]["n"], 1)
        self.assertEqual(
            self.store.q("SELECT COUNT(*) AS n FROM reports WHERE report_id LIKE 'TBL%'")[0]["n"], 1
        )

    def test_customer_api_loan_transfer_and_worker_end_to_end(self):
        with patch.dict(os.environ, {"AI_REALTIME_ENABLED": "0"}):
            application = create_app(
                tool_llm_client=self.client,
                backend_database=self.fixture.database,
                graph_database=self.graph,
                service_api_key="",
                web_password="",
            )
            with TestClient(application) as client:
                self.assertEqual(
                    client.post(
                        "/api/khach/login", json={"phone": "0900000001", "pin": "123456"}
                    ).status_code,
                    200,
                )
                loan = client.post("/api/khach/loan", json={"amount": 2_000_000})
                self.assertEqual(loan.status_code, 200, loan.text)
                response = client.post(
                    "/api/khach/transfer",
                    json={
                        "to_type": "bank",
                        "to_id": "012345678912",
                        "to_bank": "ACB",
                        "to_name": "Someone else",
                        "amount": 500_000,
                        "note": "",
                        "coached": True,
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "held")
                application.state.realtime_service.client = self.client
                for _ in range(2):
                    client.post("/api/ai/realtime/process")
                events = client.get("/api/ai/realtime/events").json()
                transfer_event = next(e for e in events if e["kind"] == "transfer")
                self.assertEqual(transfer_event["status"], "completed", transfer_event)
                result = json.loads(transfer_event["result"])
                case = json.loads(
                    self.store.q("SELECT body FROM cases WHERE alert_id=?", result["alert_id"])[0][
                        "body"
                    ]
                )
                self.assertEqual(
                    case["transaction_assessments"][0]["transfer_id"],
                    response.json()["transfer_id"],
                )
