import asyncio
import json
from app.backend.agent_tools import BackendAgentTools
from app.backend.events import publish
from app.ai.realtime import jobs
from app.ai.realtime.alerts import snapshot
from app.graph.ai_store import AIStore
from app.graph.ingestion import ingest_event
from app.ai.shield.schemas import ReportAnalysis
from app.backend.knowledge.reports import report_view
from app.backend.knowledge.recipients import related_case_count, recipient_reports
from .fixtures import RealtimeFixture


class EvidenceTests(RealtimeFixture):
    def test_exact_loan_and_held_attempt_do_not_inflate_completed_outflow(self):
        lid = self.loan()
        done = self.transfer(lid, status="done", at="2026-11-01T09:01:30", amount=900000)
        held = self.transfer(lid)
        self.loan(7000000, at="2026-11-01T09:01:45")
        alert = self.store.alert("AL1")
        alert.update(
            ts="2026-11-01T09:02:00",
            kind="transfer",
            transfer_id=held,
            context={"loan_ids": {"A": lid}},
        )
        tools = BackendAgentTools(self.store, alert)
        data = tools.call("cluster_money_flow", {})["data"]
        self.assertEqual(data["totals"]["loan_amount"], 2000000)
        self.assertEqual(data["totals"]["transfer_amount"], 900000)
        self.assertEqual(data["totals"]["held_amount"], 500000)
        self.assertEqual({r["transfer_id"] for r in data["transfers"]}, {done, held})
        self.assertEqual(
            tools.call("get_transfer", {"transfer_id": held})["data"]["transfer"]["source"][
                "table"
            ],
            "khach_transfers",
        )
        for private in ("0900000001", "001234567890", "PRIVATE"):
            self.assertNotIn(private, json.dumps(data))

    def test_same_second_future_events_do_not_leak_into_snapshot(self):
        lid = self.loan()
        publish(self.store, "loan", "KL" + str(lid), "A", "2026-11-01T09:01:00")
        first = self.transfer(lid)
        self.event(first)
        event = jobs.claim(self.store)
        event = jobs.claim(self.store)
        later = self.transfer(lid)
        self.event(later)
        future_loan = self.loan(9000000, at="2026-11-01T09:02:00")
        publish(self.store, "loan", "KL" + str(future_loan), "A", "2026-11-01T09:02:00")
        alert = snapshot(self.store, event, ["A"])
        data = BackendAgentTools(self.store, alert).call("cluster_money_flow", {})["data"]
        self.assertEqual([t["transfer_id"] for t in data["transfers"]], [first])
        self.assertEqual(data["totals"]["loan_amount"], 2000000)

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
