import os
from pathlib import Path

from dotenv import load_dotenv


def load_environment():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def configured_service_key() -> str:
    return os.environ.get("APP_API_KEY", "").strip()
