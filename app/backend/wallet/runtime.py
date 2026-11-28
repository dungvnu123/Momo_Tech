from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from fastapi import HTTPException, Request
from app import security

if TYPE_CHECKING:
    from app.backend.store import Tools
    from app.backend.integration import BackendAI


@dataclass
class WalletContext:
    tools: Tools
    adapter: BackendAI | None


def now_iso():
    return security.vntime_now().isoformat(timespec="seconds")


def me(wallet, request: Request) -> dict:
    phone = security.khach_phone(request.cookies.get(security.KHACH_COOKIE))
    rows = wallet.tools.q("SELECT * FROM khach_accounts WHERE phone=?", phone) if phone else []
    if not rows:
        raise HTTPException(401, "Cần đăng nhập ví")
    return rows[0]
