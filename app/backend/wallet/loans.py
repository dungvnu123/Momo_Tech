from fastapi import Request
from . import persistence as writes
from .runtime import me, now_iso
from .notifications import inbox_add
from .schemas import LoanIn


def current_loan(wallet, acc):
    live = wallet.tools.q(
        "SELECT loan_id, amount, disbursed_at FROM khach_loans WHERE phone=? ORDER BY loan_id DESC LIMIT 1",
        acc["phone"],
    )
    if live:
        return {**live[0], "live": True}
    a = wallet.tools.apps([acc["app_id"]])[0]
    return {"amount": int(a["amount"]), "disbursed_at": a["disbursed_at"], "live": False}


def register(router, wallet):
    @router.post("/loan")
    def take_loan(body: LoanIn, request: Request):
        acc = me(wallet, request)
        ts = now_iso()
        loan_id = writes.loan(wallet.tools, acc, body.amount, ts)
        inbox_add(
            wallet,
            acc["phone"],
            "FinVay",
            f"[FinVay] Khoan vay {body.amount:,}d da giai ngan ve vi luc {ts[11:16]}. FinVay KHONG thu phi giai ngan hay phi xac minh.".replace(
                ",", "."
            ),
            "official",
        )
        return {"ok": True, "loan_id": loan_id}
