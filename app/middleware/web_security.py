from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.security import CSP, PROTECTED, rate_limited


class WebSecurityMiddleware:
    """Web sessions, limits and response headers without buffering SSE."""
    def __init__(self, app, *, policy):
        self.app, self.policy = app, policy

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        path = request.url.path

        async def send_response(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if not path.startswith("/flows") and path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
                    headers["Content-Security-Policy"] = CSP
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if path.startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        if path.startswith("/api/") and rate_limited(request, hits=self.policy.hits, behind_proxy=self.policy.behind_proxy):
            response = JSONResponse({"detail": "Quá nhiều yêu cầu, thử lại sau ít phút"}, status_code=429,
                                    headers={"Retry-After": "60"})
        elif (self.policy.password and path.startswith(PROTECTED)
              and not self.policy.valid_session(request) and not self.policy.valid_service_key(request)):
            response = JSONResponse({"detail": "Cần đăng nhập"}, status_code=401)
        else:
            return await self.app(scope, receive, send_response)
        await response(scope, receive, send_response)
