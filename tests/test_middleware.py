import asyncio
import logging
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import test_graph_tools
from app.agents.investigation.demo import DemoInvestigationClient
from app.main import create_app
from app.middleware.request_context import RequestContextMiddleware
from app.services.tool_llm import UnconfiguredToolLLMClient


class MiddlewareTests(unittest.TestCase):
    def app(self, **options):
        return create_app(tool_llm_client=UnconfiguredToolLLMClient(), **options)

    def test_request_id_is_propagated_and_invalid_values_are_replaced(self):
        with TestClient(self.app(service_api_key="")) as client:
            response = client.get("/health", headers={"X-Request-ID": "backend-request-001"})
            self.assertEqual(response.headers["x-request-id"], "backend-request-001")
            invalid = client.get("/health", headers={"X-Request-ID": "x" * 100})
            self.assertRegex(invalid.headers["x-request-id"], r"^[0-9a-f]{32}$")

    def test_missing_and_wrong_service_keys_are_rejected_before_ai_execution(self):
        with TestClient(self.app(service_api_key="service-secret")) as client:
            for headers in ({}, {"X-API-Key": "wrong-key"}):
                response = client.post("/api/ai/shield/analyze", json={"text": "test"}, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertIn("x-request-id", response.headers)
                self.assertNotIn("service-secret", response.text)
            allowed = client.post("/api/ai/shield/analyze", json={"text": "test"},
                                  headers={"X-API-Key": "service-secret"})
            self.assertEqual(allowed.status_code, 503)

    def test_key_protects_all_api_routes_but_health_and_docs_remain_accessible(self):
        with TestClient(self.app(service_api_key="service-secret")) as client:
            for path in ("/api/v1/agents", "/api/v1/agents/ids"):
                self.assertEqual(client.get(path).status_code, 401)
                self.assertEqual(client.get(path, headers={"X-API-Key": "service-secret"}).status_code, 200)
            for path in ("/health", "/docs", "/openapi.json"):
                self.assertEqual(client.get(path).status_code, 200)

    def test_local_mode_does_not_require_a_key(self):
        with TestClient(self.app(service_api_key="")) as client:
            self.assertEqual(client.get("/api/v1/agents").status_code, 200)

    def test_model_key_is_not_the_service_key(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "model-secret", "APP_API_KEY": "service-secret"}):
            with TestClient(self.app()) as client:
                self.assertEqual(client.get("/api/v1/agents", headers={"X-API-Key": "model-secret"}).status_code, 401)
                self.assertEqual(client.get("/api/v1/agents", headers={"X-API-Key": "service-secret"}).status_code, 200)

    def test_swagger_documents_auth_without_exposing_the_key(self):
        with TestClient(self.app(service_api_key="service-secret")) as client:
            response = client.get("/openapi.json")
            self.assertNotIn("service-secret", response.text)
            schema = response.json()
            self.assertEqual(schema["components"]["securitySchemes"]["ServiceApiKey"]["name"], "X-API-Key")
            self.assertEqual(schema["paths"]["/api/investigations"]["post"]["security"], [{"ServiceApiKey": []}])

    def test_access_log_contains_metadata_without_payload_credentials_or_query(self):
        with TestClient(self.app(service_api_key="")) as client:
            with self.assertLogs("app.requests", level=logging.INFO) as captured:
                client.post("/api/ai/shield/analyze?token=query-private", json={"text": "payload-private"},
                            headers={"X-API-Key": "header-private", "X-Request-ID": "trace-001"})
        record = captured.records[-1]
        self.assertEqual(record.request_id, "trace-001")
        self.assertEqual(record.route, "/shield/analyze")
        self.assertEqual(record.operation, "app.controller.ai.shield.analyze_report")
        self.assertEqual(record.status_code, 503)
        self.assertGreaterEqual(record.duration_ms, 0)
        for secret in ("payload-private", "header-private", "query-private"):
            self.assertNotIn(secret, str(record.__dict__))

    def test_unhandled_error_has_a_safe_response_and_request_id(self):
        application = self.app(service_api_key="", backend_database=False)

        @application.get("/explode")
        async def explode():
            raise RuntimeError("private-provider-detail")

        with TestClient(application, raise_server_exceptions=False) as client:
            response = client.get("/explode", headers={"X-Request-ID": "error-trace"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["x-request-id"], "error-trace")
        self.assertEqual(response.json()["request_id"], "error-trace")
        self.assertNotIn("private-provider-detail", response.text)

    def test_authenticated_investigation_still_streams_sse(self):
        fixture = test_graph_tools.GraphToolTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        application = create_app(tool_llm_client=DemoInvestigationClient(), graph_database=fixture.database,
                                 service_api_key="service-secret")
        with TestClient(application) as client:
            response = client.post("/api/investigations", json={"app_id": "A", "streamResponse": True},
                                   headers={"X-API-Key": "service-secret", "X-Request-ID": "stream-001"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "stream-001")
        self.assertIn("event: tool_result", response.text)
        self.assertIn("event: done", response.text)


class ASGIStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_callable_object_endpoint_does_not_break_request_logging(self):
        sent = []

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b""}

        scope = {"type": "http", "method": "GET", "path": "/static", "headers": [],
                 "endpoint": SimpleNamespace(), "route": SimpleNamespace(path="/static")}
        await RequestContextMiddleware(downstream)(scope, receive, send)
        self.assertEqual(sent[-1]["body"], b"ok")

    async def test_response_chunks_are_forwarded_immediately_without_buffering(self):
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b""}

        async def downstream(scope, receive, send_response):
            await send_response({"type": "http.response.start", "status": 200, "headers": []})
            await send_response({"type": "http.response.body", "body": b"first", "more_body": True})
            self.assertEqual(len(sent), 2)
            await asyncio.sleep(0)
            await send_response({"type": "http.response.body", "body": b"second", "more_body": False})

        scope = {"type": "http", "method": "POST", "path": "/events", "headers": [],
                 "route": SimpleNamespace(path="/events")}
        await RequestContextMiddleware(downstream)(scope, receive, send)
        self.assertEqual([message["body"] for message in sent[1:]], [b"first", b"second"])
        self.assertTrue(re.fullmatch(r"[0-9a-f]{32}", scope["state"]["request_id"]))

    async def test_concurrent_requests_have_isolated_context(self):
        identifiers = []

        async def downstream(scope, receive, send):
            await asyncio.sleep(0)
            identifiers.append(scope["state"]["request_id"])
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def send(message):
            pass

        async def receive():
            return {"type": "http.request", "body": b""}

        middleware = RequestContextMiddleware(downstream)
        await asyncio.gather(*(middleware({"type": "http", "method": "GET", "path": "/health", "headers": []},
                                         receive, send) for _ in range(5)))
        self.assertEqual(len(set(identifiers)), 5)


if __name__ == "__main__":
    unittest.main()
