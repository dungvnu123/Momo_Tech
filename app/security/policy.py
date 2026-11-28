import os
import hmac
import secrets
from collections import defaultdict, deque
from .config import COOKIE, PUBLIC_API
from .sessions import valid_token


class WebSecurityPolicy:
    def __init__(self, *, password=None, secret=None, service_api_key=""):
        self.password = os.environ.get("THIENLA_PASSWORD", "") if password is None else password
        self.secret = (secret or os.environ.get("THIENLA_SECRET") or secrets.token_hex(32)).encode()
        self.behind_proxy = bool(os.environ.get("THIENLA_BEHIND_PROXY"))
        self.service_key = service_api_key.encode()
        self.hits = defaultdict(deque)

    def valid_session(self, request):
        return valid_token(request.cookies.get(COOKIE), secret=self.secret)

    def valid_service_key(self, request):
        return bool(self.service_key) and hmac.compare_digest(
            request.headers.get("X-API-Key", "").encode(), self.service_key
        )

    def public_api(self, path):
        return path in PUBLIC_API or path.startswith(
            ("/api/shield/", "/api/ai/shield/", "/api/khach/")
        )
