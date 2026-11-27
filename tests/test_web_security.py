import asyncio
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import test_backend_integration as fixtures
from app.main import create_app
from app.middleware.web_security import WebSecurityMiddleware
from app.security import COOKIE, TTL, WebSecurityPolicy, make_token, valid_token
from app.services.tool_llm import UnconfiguredToolLLMClient
from test_investigation import ScriptedClient, detailed_submission, turn


class WebSecurityTests(unittest.TestCase):
    def app(self, **options):
        return create_app(tool_llm_client=UnconfiguredToolLLMClient(), backend_database=False,
                          service_api_key=options.pop("service_api_key", ""),
                          web_password=options.pop("web_password", "test-password"),
                          web_secret="test-session-signing-key", **options)

    def client(self, **options):
        return self.enterContext(TestClient(self.app(**options)))

    def test_login_logout_and_sensitive_ai_routes(self):
        client = self.client()
        self.assertEqual(client.get("/api/me").json(), {"auth_required": True, "logged_in": False})
        for path in ("/api/v1/agents", "/api/alerts", "/api/apps/A", "/api/live"):
            self.assertEqual(client.get(path).status_code, 401)
        for path in ("/api/investigations", "/api/ai/entities/resolve", "/api/ai/triage", "/api/ai/transfer/check"):
            self.assertEqual(client.post(path, json={}).status_code, 401)
        response = client.post("/api/login", json={"password": "test-password"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=strict", response.headers["set-cookie"])
        self.assertEqual(client.get("/api/v1/agents").status_code, 200)
        self.assertTrue(client.get("/api/me").json()["logged_in"])
        self.assertEqual(client.post("/api/logout").status_code, 200)
        self.assertEqual(client.get("/api/v1/agents").status_code, 401)

    def test_shield_and_health_remain_public_while_docs_close_in_password_mode(self):
        client = self.client()
        self.assertEqual(client.get("/health").status_code, 200)
        response = client.post("/api/ai/shield/analyze", json={"text": "Fictional message"})
        self.assertEqual(response.status_code, 503)  # Reaches unconfigured model, not an auth rejection.
        for path in ("/docs", "/redoc", "/openapi.json"):
            self.assertEqual(client.get(path).status_code, 404)

    def test_service_key_and_web_session_are_both_supported(self):
        client = self.client(service_api_key="test-service-key")
        self.assertEqual(client.get("/api/v1/agents").status_code, 401)
        self.assertEqual(client.get("/api/v1/agents", headers={"X-API-Key": "test-service-key"}).status_code, 200)
        self.assertEqual(client.get("/api/me").status_code, 200)
        self.assertEqual(client.post("/api/login", json={"password": "test-password"}).status_code, 200)
        self.assertEqual(client.get("/api/v1/agents").status_code, 200)
        self.assertEqual(client.post("/api/logout").status_code, 200)
        self.assertEqual(client.get("/api/v1/agents").status_code, 401)

    def test_login_rate_limit_is_per_app_and_does_not_trust_forwarded_ip_by_default(self):
        with patch.dict("os.environ", {"THIENLA_BEHIND_PROXY": ""}):
            client = self.client()
        for index in range(5):
            self.assertEqual(client.post("/api/login", json={"password": "wrong"},
                                        headers={"X-Forwarded-For": f"192.0.2.{index}"}).status_code, 401)
        response = client.post("/api/login", json={"password": "test-password"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "60")
        other = self.client()
        self.assertEqual(other.post("/api/login", json={"password": "test-password"}).status_code, 200)

    def test_tampered_expired_or_non_ascii_session_is_rejected(self):
        secret = b"test-signing-key"
        token = make_token(secret=secret)
        self.assertTrue(valid_token(token, secret=secret))
        for candidate in (None, "", "invalid", token + "a", "é.invalid", token.replace(".", ".é", 1)):
            self.assertFalse(valid_token(candidate, secret=secret))
        self.assertFalse(valid_token(token, secret=b"another-key"))
        with patch("app.security.time.time", return_value=time.time() + TTL + 1):
            self.assertFalse(valid_token(token, secret=secret))

    def test_https_login_cookie_is_secure(self):
        with TestClient(self.app(), base_url="https://testserver") as client:
            response = client.post("/api/login", json={"password": "test-password"})
            self.assertIn("Secure", response.headers["set-cookie"])
            self.assertEqual(client.get("/api/v1/agents").status_code, 200)

    def test_response_headers_cover_auth_errors_and_normal_responses(self):
        client = self.client()
        for response in (client.get("/api/v1/agents"), client.get("/health")):
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
            self.assertEqual(response.headers["referrer-policy"], "no-referrer")
            self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
            self.assertIn("x-request-id", response.headers)

    def test_invalid_backend_inputs_are_rejected_before_queries_or_ai(self):
        fixture = fixtures.BackendIntegrationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        model = ScriptedClient()
        client = fixture.client(model)
        for identifier in ("unknown", "CK1", "CK00001' OR 1=1"):
            self.assertEqual(client.post("/api/transfer/check", json={"transfer_id": identifier}).status_code, 422)
        self.assertEqual(client.post("/api/shield/analyze", json={"text": "x" * 4001}).status_code, 422)
        self.assertEqual(client.get("/api/apps/A", params={"as_of": "invalid"}).status_code, 400)
        self.assertEqual(client.get("/api/live", params={"start": "invalid"}).status_code, 400)
        self.assertEqual(model.history, [])

    def test_authenticated_backend_investigation_keeps_its_sse_contract(self):
        fixture = fixtures.BackendIntegrationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        model = ScriptedClient(turn("read-1", "cluster_money_flow", {}), turn("finish", "submit_case", detailed_submission(
            verdict="victims", victims=["A"], actions=["Support customer"])))
        app = create_app(tool_llm_client=model, backend_database=fixture.database, service_api_key="",
                         web_password="test-password", web_secret="test-session-key")
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/alerts/AL1/investigate").status_code, 401)
            self.assertEqual(client.post("/api/login", json={"password": "test-password"}).status_code, 200)
            response = client.get("/api/alerts/AL1/investigate")
            self.assertEqual(response.status_code, 200)
            self.assertIn('"type": "step"', response.text)
            self.assertIn('"type": "case"', response.text)
            self.assertIn('"status": "completed"', response.text)
            self.assertEqual(client.get("/flows/").status_code, 200)


class SecurityStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_security_headers_do_not_buffer_sse_chunks(self):
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b""}

        async def downstream(scope, receive, send_response):
            await send_response({"type": "http.response.start", "status": 200, "headers": []})
            await send_response({"type": "http.response.body", "body": b"first", "more_body": True})
            self.assertEqual(sent[-1]["body"], b"first")
            await asyncio.sleep(0)
            await send_response({"type": "http.response.body", "body": b"second", "more_body": False})

        policy = WebSecurityPolicy(password="", secret="test-key")
        scope = {"type": "http", "method": "GET", "path": "/api/live", "query_string": b"",
                 "scheme": "http", "server": ("localhost", 80), "client": ("testclient", 1), "headers": []}
        await WebSecurityMiddleware(downstream, policy=policy)(scope, receive, send)
        self.assertEqual([x["body"] for x in sent[1:]], [b"first", b"second"])
