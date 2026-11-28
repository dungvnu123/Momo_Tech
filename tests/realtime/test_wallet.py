import json
import os
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.ai.shield.schemas import ReportAnalysis
from app.backend.knowledge.reports import report_view
from app.main import create_app
from .fixtures import RealtimeFixture


class WalletTests(RealtimeFixture):
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
            patch("app.backend.wallet.inbox.ai_report", new=AsyncMock(return_value=result)),
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
                loan = client.post("/api/khach/loan", json={"amount": 2000000})
                self.assertEqual(loan.status_code, 200, loan.text)
                response = client.post(
                    "/api/khach/transfer",
                    json={
                        "to_type": "bank",
                        "to_id": "012345678912",
                        "to_bank": "ACB",
                        "to_name": "Someone else",
                        "amount": 500000,
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
                transfer_event = next((e for e in events if e["kind"] == "transfer"))
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
