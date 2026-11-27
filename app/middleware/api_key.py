from hmac import compare_digest

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ServiceKeyMiddleware:
    def __init__(self, app: ASGIApp, *, api_key: str):
        self.app = app
        self._key = api_key.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            supplied = Headers(scope=scope).get("x-api-key", "").encode("utf-8")
            if not compare_digest(supplied, self._key):
                response = JSONResponse({"detail": "Invalid service API key"}, status_code=401)
                return await response(scope, receive, send)
        await self.app(scope, receive, send)
