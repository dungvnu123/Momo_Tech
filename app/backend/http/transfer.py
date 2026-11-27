from fastapi import HTTPException
from pydantic import BaseModel
from app.core.http import run_ai
from .. import mock_ai as ai
from ..store import mask
from .common import times_reported


def register(app, tools, adapter, META):
    class TransferIn(BaseModel):
        transfer_id: str


    def transfer_ctx(t):
        a = tools.q("SELECT * FROM apps WHERE phone=?", t["from_wallet"])[0]
        from datetime import datetime
        m = (datetime.fromisoformat(t["created_at"]) - datetime.fromisoformat(a["disbursed_at"])).total_seconds() / 60
        return a, {"amount": int(t["amount"]), "loan_amount": int(a["amount"]), "minutes_after_disbursal": round(m),
                   "to_name_matches_borrower": t["to_name"] == ai.plain(a["full_name"]).upper(),
                   "recipient_in_contacts": t["recipient_in_contacts"] == "True",
                   "contact_saved_minutes_ago": int(t["contact_saved_minutes_ago"]) if t["contact_saved_minutes_ago"] else None,
                   "prior_transfers_to_recipient": int(t["prior_transfers_to_recipient"]), "simo_flag": t["simo_flag"] == "True",
                   "to_wallet_age_days": t["to_wallet_age_days"], "note": t["note"], "times_reported": times_reported(tools, [t["to_id"]], t["created_at"])}


    @app.get("/api/transfer/samples")
    def transfer_samples():
        """Vài giao dịch thật trong dữ liệu, chọn theo TÍN HIỆU (không dùng đáp án) để demo đủ 3 mức."""
        picks = {
            "SIMO gắn cờ": "simo_flag='True'",
            "Người lạ, vừa lưu số": "recipient_in_contacts='True' AND CAST(contact_saved_minutes_ago AS INT) < 120 AND prior_transfers_to_recipient='0' AND to_type='bank'",
            "Ví nhận mới mở": "to_type='momo_wallet' AND CAST(to_wallet_age_days AS INT) <= 7 AND prior_transfers_to_recipient='0'",
            "Trả tiền phòng quen": "note LIKE 'tien phong%' AND CAST(prior_transfers_to_recipient AS INT) > 2 AND recipient_in_contacts='True' AND CAST(contact_saved_minutes_ago AS INT) > 1440",
            "Rút về tài khoản chính chủ": "to_type='bank' AND CAST(prior_transfers_to_recipient AS INT) > 5",
        }
        fresh = lambda c: c["amount"] >= 0.8 * c["loan_amount"] and c["minutes_after_disbursal"] <= 120
        want = {"Trả tiền phòng quen": lambda c: True, "Rút về tài khoản chính chủ": lambda c: c["to_name_matches_borrower"] and fresh(c)}
        out = []
        for label, cond in picks.items():
            for t in tools.q(f"SELECT * FROM transfers WHERE {cond} ORDER BY transfer_id LIMIT 600"):
                a, ctx = transfer_ctx(t)
                if want.get(label, fresh)(ctx):
                    out.append({"label": label, "transfer_id": t["transfer_id"], "to_name": t["to_name"], "to_bank": t["to_bank"],
                                "to_id": mask(t["to_id"]), "amount": ctx["amount"], "loan_amount": ctx["loan_amount"],
                                "minutes_after_disbursal": ctx["minutes_after_disbursal"], "note": t["note"]})
                    break
        return out


    @app.post("/api/transfer/check")
    async def transfer_check(body: TransferIn):
        rows = tools.q("SELECT * FROM transfers WHERE transfer_id=?", body.transfer_id)
        if not rows:
            raise HTTPException(404, "Không thấy giao dịch")
        _, ctx = transfer_ctx(rows[0])
        return {"context": ctx, **(await run_ai(adapter.check_transfer(ctx)))}
