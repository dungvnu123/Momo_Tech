# path: app/security.py
"""Bảo mật tối thiểu cho bản thi: đăng nhập, phiên ký HMAC, giới hạn lượt gọi, header bảo mật.

Cấu hình qua biến môi trường (đặt trong .env trên VPS, KHÔNG commit):
  THIENLA_PASSWORD  mật khẩu màn đội rủi ro. Không đặt → chế độ dev mở (in cảnh báo khi khởi động).
  THIENLA_SECRET    khoá ký phiên. Không đặt → sinh ngẫu nhiên mỗi lần khởi động (phiên cũ mất hiệu lực).
Giới hạn lượt gọi giữ trong RAM từng app; chạy nhiều tiến trình thì cần kho dùng chung.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

PASSWORD = os.environ.get("THIENLA_PASSWORD", "")
SECRET = (os.environ.get("THIENLA_SECRET") or secrets.token_hex(32)).encode()
COOKIE, TTL = "tl_session", 8 * 3600

# Cần đăng nhập: mọi thứ chạm tới dữ liệu hồ sơ. Công khai: Lá chắn (cho khách vay), tổng quan + chỉ số (chỉ số đếm tổng hợp).
PROTECTED = ("/api/alerts", "/api/apps", "/api/transfer", "/api/live",
             "/api/investigations", "/api/v1/agents", "/api/ai/entities", "/api/ai/triage", "/api/ai/transfer")
PUBLIC_API = ("/api/login", "/api/logout", "/api/me", "/api/overview", "/api/metrics")
# (tiền tố, số lượt, trong bao nhiêu giây) — khớp tiền tố đầu tiên
LIMITS = [("/api/login", 5, 60), ("/api/shield/analyze", 30, 60), ("/api/ai/shield/analyze", 30, 60),
          ("/api/live", 6, 60), ("/investigate", 12, 60), ("/api/investigations", 12, 60),
          ("/api/v1/agents/run", 12, 60), ("/api/ai/entities", 30, 60), ("/api/ai/triage", 30, 60),
          ("/api/ai/transfer/check", 60, 60), ("/api/transfer/check", 60, 60), ("/api/", 600, 60)]
_hits: dict = defaultdict(deque)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'")


def make_token(*, secret=None) -> str:
    exp = str(int(time.time()) + TTL)
    return exp + "." + hmac.new(SECRET if secret is None else secret, exp.encode(), hashlib.sha256).hexdigest()


def valid_token(tok: str | None, *, secret=None) -> bool:
    if not tok or not re.fullmatch(r"[0-9]{1,12}\.[a-f0-9]{64}", tok):
        return False
    exp, sig = tok.split(".", 1)
    good = hmac.new(SECRET if secret is None else secret, exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and exp.isdigit() and int(exp) > time.time()


def check_password(pw: str, *, password=None) -> bool:
    expected = PASSWORD if password is None else password
    return bool(expected) and hmac.compare_digest(pw.encode(), expected.encode())


def client_ip(req: Request, *, behind_proxy=None) -> str:
    # Sau reverse proxy (Caddy) thì lấy IP thật từ X-Forwarded-For — chỉ tin khi proxy là của mình.
    fwd = req.headers.get("x-forwarded-for")
    trusted = bool(os.environ.get("THIENLA_BEHIND_PROXY")) if behind_proxy is None else behind_proxy
    return fwd.split(",")[0].strip() if fwd and trusted else (req.client.host if req.client else "?")


def rate_limited(req: Request, *, hits=None, behind_proxy=None) -> bool:
    path = req.url.path
    for prefix, n, win in LIMITS:
        if prefix in path:
            buckets = _hits if hits is None else hits
            q, now = buckets[(client_ip(req, behind_proxy=behind_proxy), prefix)], time.monotonic()
            while q and q[0] < now - win:
                q.popleft()
            if len(q) >= n:
                return True
            q.append(now)
            return False
    return False


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
            request.headers.get("X-API-Key", "").encode(), self.service_key)

    def public_api(self, path):
        return path in PUBLIC_API or path.startswith(("/api/shield/", "/api/ai/shield/"))


async def guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and rate_limited(request):
        return JSONResponse({"detail": "Quá nhiều yêu cầu, thử lại sau ít phút"}, status_code=429)
    if PASSWORD and path.startswith(PROTECTED) and not valid_token(request.cookies.get(COOKIE)):
        return JSONResponse({"detail": "Cần đăng nhập"}, status_code=401)
    resp = await call_next(request)
    if not path.startswith("/flows"):   # feature-flow tự đặt CSP riêng (băm script nội tuyến)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp
