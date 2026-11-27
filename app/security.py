# path: app/security.py
"""Bảo mật tối thiểu cho bản thi: đăng nhập, phiên ký HMAC, giới hạn lượt gọi, header bảo mật.

Cấu hình qua biến môi trường (đặt trong .env trên VPS, KHÔNG commit):
  THIENLA_PASSWORD  mật khẩu màn đội rủi ro. Không đặt → chế độ dev mở (in cảnh báo khi khởi động).
  THIENLA_SECRET    khoá ký phiên. Không đặt → sinh ngẫu nhiên mỗi lần khởi động (phiên cũ mất hiệu lực).
ponytail: giới hạn lượt gọi giữ trong RAM của 1 tiến trình; chạy nhiều tiến trình thì chuyển sang Redis.
"""
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

PASSWORD = os.environ.get("THIENLA_PASSWORD", "")
SECRET = (os.environ.get("THIENLA_SECRET") or secrets.token_hex(32)).encode()
COOKIE, TTL = "tl_session", 8 * 3600
if not PASSWORD:
    print("⚠️  THIENLA_PASSWORD chưa đặt — màn đội rủi ro đang MỞ (chỉ dùng khi chạy local).")

# Cần đăng nhập: mọi thứ chạm tới dữ liệu hồ sơ. Công khai: Lá chắn (cho khách vay), tổng quan + chỉ số (chỉ số đếm tổng hợp).
PROTECTED = ("/api/alerts", "/api/apps", "/api/transfer", "/api/live")
# (tiền tố, số lượt, trong bao nhiêu giây) — khớp tiền tố đầu tiên
LIMITS = [("/api/login", 5, 60), ("/api/shield/analyze", 30, 60), ("/api/live", 6, 60),
          ("/investigate", 12, 60), ("/api/transfer/check", 60, 60), ("/api/", 600, 60)]
_hits: dict = defaultdict(deque)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'")


def make_token() -> str:
    exp = str(int(time.time()) + TTL)
    return exp + "." + hmac.new(SECRET, exp.encode(), hashlib.sha256).hexdigest()


def valid_token(tok: str | None) -> bool:
    if not tok or "." not in tok:
        return False
    exp, sig = tok.split(".", 1)
    good = hmac.new(SECRET, exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and exp.isdigit() and int(exp) > time.time()


def check_password(pw: str) -> bool:
    return bool(PASSWORD) and hmac.compare_digest(pw.encode(), PASSWORD.encode())


def client_ip(req: Request) -> str:
    # Sau reverse proxy (Caddy) thì lấy IP thật từ X-Forwarded-For — chỉ tin khi proxy là của mình.
    fwd = req.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd and os.environ.get("THIENLA_BEHIND_PROXY") else (req.client.host if req.client else "?")


def rate_limited(req: Request) -> bool:
    path = req.url.path
    for prefix, n, win in LIMITS:
        if prefix in path:
            q, now = _hits[(client_ip(req), prefix)], time.time()
            while q and q[0] < now - win:
                q.popleft()
            if len(q) >= n:
                return True
            q.append(now)
            return False
    return False


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
