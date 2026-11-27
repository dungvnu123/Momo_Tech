from hmac import compare_digest

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request


class ServiceKeyMiddleware:
    def __init__(self, app: ASGIApp, *, api_key: str, web_policy=None):
        self.app = app
        self._key = api_key.encode("utf-8")
        self.web_policy = web_policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            if self.web_policy and self.web_policy.password:
                request = Request(scope)
                if self.web_policy.public_api(scope["path"]) or self.web_policy.valid_session(request):
                    return await self.app(scope, receive, send)
            supplied = Headers(scope=scope).get("x-api-key", "").encode("utf-8")
            if not compare_digest(supplied, self._key):
                response = JSONResponse({"detail": "Invalid service API key"}, status_code=401)
                return await response(scope, receive, send)
        await self.app(scope, receive, send)
