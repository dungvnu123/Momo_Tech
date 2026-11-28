from fastapi import Request
from .runtime import me, now_iso
from .loans import current_loan


def register(router, wallet):
    @router.get("/me")
    def profile(request: Request):
        acc = me(wallet, request)
        loan = current_loan(wallet, acc)
        nxt = wallet.tools.q(
            "SELECT term_no, due_date, total_due FROM schedule WHERE app_id=? AND due_date >= ? ORDER BY due_date LIMIT 1",
            acc["app_id"],
            now_iso()[:10],
        )
        unread = wallet.tools.q(
            "SELECT COUNT(*) AS n FROM khach_inbox WHERE phone=? AND NOT is_read", acc["phone"]
        )[0]["n"]
        contacts = wallet.tools.q(
            "SELECT contact_phone, name, saved_at FROM khach_contacts WHERE phone=? ORDER BY saved_at",
            acc["phone"],
        )
        return {
            "name": acc["display_name"],
            "phone": acc["phone"],
            "balance": acc["balance"],
            "loan": loan,
            "next_due": nxt[0] if nxt else None,
            "unread": unread,
            "contacts": contacts,
        }
