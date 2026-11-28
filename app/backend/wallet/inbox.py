from fastapi import HTTPException, Request
from . import persistence as writes
from .runtime import me, now_iso
from .notifications import live_alert
from .decisions import ai_report
from .recipients import times_reported


def register(router, wallet):
    @router.get("/inbox")
    def inbox(request: Request):
        acc = me(wallet, request)
        return wallet.tools.q(
            "SELECT msg_id, ts, sender, body, kind, is_read, reported_verdict FROM khach_inbox WHERE phone=? ORDER BY ts DESC",
            acc["phone"],
        )

    @router.post("/inbox/{msg_id}/read")
    def read_msg(msg_id: int, request: Request):
        acc = me(wallet, request)
        wallet.tools.run(
            "UPDATE khach_inbox SET is_read=TRUE WHERE msg_id=? AND phone=?", msg_id, acc["phone"]
        )
        return {"ok": True}

    @router.post("/report/{msg_id}")
    async def report_msg(msg_id: int, request: Request):
        acc = me(wallet, request)
        rows = wallet.tools.q(
            "SELECT body, kind FROM khach_inbox WHERE msg_id=? AND phone=?", msg_id, acc["phone"]
        )
        if not rows:
            raise HTTPException(404, "Không thấy tin nhắn")
        res = await ai_report(wallet, rows[0]["body"], rows[0]["kind"] == "official")
        ind = res["indicators"]
        seen_before = times_reported(wallet, ind["accounts"] + ind["phones"])

        def notify():
            acc_txt = ", ".join(ind["accounts"] + ind["phones"] + ind["urls"]) or "—"
            return live_alert(
                wallet,
                "report",
                acc["app_id"],
                f"Khách báo lừa đảo qua app — tài khoản {acc_txt}"
                + (f" (đã bị báo {seen_before} lần)" if seen_before else ""),
                "; ".join(res["reasons"]),
                "khan" if seen_before else "cao",
                0.85 if seen_before else 0.6,
                ["user_report"],
                n_reports=seen_before + 1,
            )

        saved = writes.report(wallet.tools, acc, msg_id, rows[0]["body"], res, now_iso(), notify)
        return {**saved, "times_reported": seen_before}
