import asyncio
import json
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.backend.events import publish
from app.ai.realtime import jobs
from app.graph.ai_store import AIStore
from app.main import create_app
from app.services.tool_llm import UnconfiguredToolLLMClient
from .fixtures import RealtimeFixture


class WorkerTests(RealtimeFixture):
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
