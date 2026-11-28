import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from .fixtures import RealtimeFixture


class WalletIsolationTests(RealtimeFixture):
    def test_two_apps_keep_wallet_connections_separate(self):
        other = RealtimeFixture()
        other.setUp()
        self.addCleanup(other.doCleanups)
        with patch.dict(os.environ, {"AI_REALTIME_ENABLED": "0"}):
            first_app = create_app(
                tool_llm_client=self.client,
                backend_database=self.fixture.database,
                graph_database=self.graph,
                service_api_key="",
                web_password="",
            )
            second_app = create_app(
                tool_llm_client=other.client,
                backend_database=other.fixture.database,
                graph_database=other.graph,
                service_api_key="",
                web_password="",
            )
            with TestClient(first_app) as first, TestClient(second_app) as second:
                for client in (first, second):
                    response = client.post(
                        "/api/khach/login", json={"phone": "0900000001", "pin": "123456"}
                    )
                    self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    first.post("/api/khach/loan", json={"amount": 1_000_000}).status_code,
                    200,
                )
                self.assertEqual(self.store.q("SELECT COUNT(*) AS n FROM khach_loans")[0]["n"], 1)
                self.assertEqual(other.store.q("SELECT COUNT(*) AS n FROM khach_loans")[0]["n"], 0)
                self.assertEqual(
                    second.post("/api/khach/loan", json={"amount": 2_000_000}).status_code,
                    200,
                )
                self.assertEqual(
                    other.store.q("SELECT amount FROM khach_loans")[0]["amount"], 2_000_000
                )
