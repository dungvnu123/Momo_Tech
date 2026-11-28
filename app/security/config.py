import os
import secrets
from app.db.config import load_env

load_env()
COOKIE, TTL = "tl_session", 8 * 3600
KHACH_COOKIE, KHACH_TTL = "tl_khach", 2 * 3600
PASSWORD = os.environ.get("THIENLA_PASSWORD", "")

SECRET = (os.environ.get("THIENLA_SECRET") or secrets.token_hex(32)).encode()

DEMO_AUTOFILL = os.environ.get("DEMO_AUTOFILL") == "1"

PROTECTED = (
    "/api/alerts",
    "/api/apps",
    "/api/transfer",
    "/api/live",
    "/api/investigations",
    "/api/v1/agents",
    "/api/ai/entities",
    "/api/ai/triage",
    "/api/ai/transfer",
    "/api/ai/pipeline",
    "/api/sim",
    "/api/ai/realtime",
)

PUBLIC_API = ("/api/login", "/api/logout", "/api/me", "/api/overview", "/api/metrics")

LIMITS = [
    ("/api/login", 5, 60),
    ("/api/khach/login", 5, 60),
    ("/api/khach/transfer", 20, 60),
    ("/api/khach/report", 20, 60),
    ("/api/khach/lookup", 20, 60),
    ("/api/shield/analyze", 30, 60),
    ("/api/ai/shield/analyze", 30, 60),
    ("/api/live", 6, 60),
    ("/investigate", 12, 60),
    ("/api/investigations", 12, 60),
    ("/api/ai/pipeline/run", 2, 60),
    ("/api/v1/agents/run", 12, 60),
    ("/api/ai/entities", 30, 60),
    ("/api/ai/triage", 30, 60),
    ("/api/ai/transfer/check", 60, 60),
    ("/api/transfer/check", 60, 60),
    ("/api/", 600, 60),
]

CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
