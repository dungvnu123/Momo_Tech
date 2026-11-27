import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.requests")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", incoming) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started, status, completed = perf_counter(), 500, False

        async def send_response(message: Message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_response)
            completed = True
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            endpoint = scope.get("endpoint")
            operation = "unmatched"
            if endpoint is not None:
                module = getattr(endpoint, "__module__", type(endpoint).__module__)
                name = getattr(endpoint, "__qualname__", type(endpoint).__qualname__)
                operation = f"{module}.{name}"
            logger.info("HTTP request completed", extra={
                "request_id": request_id, "method": scope["method"], "route": route,
                "operation": operation,
                "status_code": status, "duration_ms": round((perf_counter() - started) * 1000, 2),
                "completed": completed,
            })
