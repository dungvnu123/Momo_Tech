import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path=ROOT / ".env"):
    """Nạp .env nhưng KHÔNG ghi đè biến môi trường đã đặt."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and (not line.lstrip().startswith("#")) and ("=" in line):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "Thiếu DATABASE_URL — chép .env.example thành .env rồi `docker compose up -d db`"
        )
    return url


load_env()
