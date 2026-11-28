import time
from datetime import datetime
from fastapi import HTTPException, Request
from app import security
from app.backend import mock_ai as ai
from . import persistence as writes
from .runtime import me, now_iso
from .notifications import inbox_add, live_alert
from .loans import current_loan
from .decisions import ai_transfer
from .schemas import TransferIn
from app.backend.knowledge.recipients import related_case_count, recipient_reports
from app.graph.normalize import account as recipient_identity


def execute_transfer(wallet, acc: dict, body: TransferIn, source: str = "app") -> dict:
    """Thực hiện giao dịch mô phỏng bằng luật, không gọi LLM."""
    t0 = time.perf_counter()
    ctx = build_ctx(wallet, acc, body)
    chk = {
        **ai.check_transfer(ctx),
        "mode": "luật (mô phỏng)",
        "latency_ms": round((time.perf_counter() - t0) * 1000),
    }
    return commit_transfer(wallet, acc, body, ctx, chk, source)


def build_ctx(wallet, acc: dict, body: TransferIn) -> dict:
    """Ngữ cảnh THẬT tại lúc chuyển. acc cần: phone, app_id, display_name, balance (None = không theo dõi số dư)."""
    to_id = ai.norm_number(body.to_id)
    if not to_id.isdigit():
        raise HTTPException(422, "Số tài khoản/ví chỉ gồm chữ số")
    try:
        recipient_identity(body.to_type, body.to_bank, to_id)
        if not 8 <= len(to_id) <= 19:
            raise ValueError("Invalid length")
    except ValueError:
        raise HTTPException(
            422, "Cần đúng số tài khoản/ví, loại người nhận và mã ngân hàng"
        ) from None
    if body.save_contact:
        wallet.tools.run(
            "INSERT INTO khach_contacts VALUES (?,?,?,?) ON CONFLICT (phone, contact_phone) DO NOTHING",
            acc["phone"],
            to_id,
            body.to_name,
            now_iso(),
        )
    loan, now = (current_loan(wallet, acc), security.vntime_now())
    exact_reports, unscoped_reports = recipient_reports(
        wallet.tools, body.to_type, body.to_bank, to_id, now.isoformat(timespec="seconds")
    )
    contact = wallet.tools.q(
        "SELECT saved_at FROM khach_contacts WHERE phone=? AND contact_phone=?", acc["phone"], to_id
    )
    prior = wallet.tools.q(
        "SELECT COUNT(*) AS n FROM khach_transfers WHERE phone=? AND to_id=? AND status='done'",
        acc["phone"],
        to_id,
    )[0]["n"]
    prior += wallet.tools.q(
        "SELECT COUNT(*) AS n FROM transfers WHERE from_wallet=? AND to_id=?", acc["phone"], to_id
    )[0]["n"]
    ctx = {
        "amount": body.amount,
        "loan_amount": loan["amount"],
        "loan_id": loan.get("loan_id"),
        "minutes_after_disbursal": round(
            (now - datetime.fromisoformat(loan["disbursed_at"])).total_seconds() / 60
        ),
        "to_name_matches_borrower": ai.plain(body.to_name).upper()
        == ai.plain(acc["display_name"]).upper(),
        "recipient_in_contacts": bool(contact),
        "contact_saved_minutes_ago": round(
            (now - datetime.fromisoformat(contact[0]["saved_at"])).total_seconds() / 60
        )
        if contact
        else None,
        "prior_transfers_to_recipient": prior,
        "simo_flag": bool(wallet.tools.q("SELECT 1 FROM simo_list WHERE to_id=?", to_id)),
        "to_wallet_age_days": None,
        "note": body.note,
        "times_reported": exact_reports,
        "unscoped_report_count": unscoped_reports,
        "balance": acc.get("balance"),
        "to_id": to_id,
        "coached": body.coached,
        "unverified_case_count": related_case_count(
            wallet.tools, body.to_type, body.to_bank, to_id
        ),
        "ring_case": (
            wallet.tools.q(
                "SELECT cid, verdict, n_senders FROM ring_accounts WHERE to_id=? ORDER BY n_senders DESC LIMIT 1",
                to_id,
            )
            or [None]
        )[0],
    }
    return ctx


def commit_transfer(
    wallet, acc: dict, body: TransferIn, ctx: dict, chk: dict, source: str = "app"
) -> dict:
    """Ghi giao dịch theo quyết định; tạm giữ thì sinh cảnh báo cho đội rủi ro."""
    if body.coached:
        chk = {
            **chk,
            "decision": "hold",
            "reasons": [
                "Bạn cho biết đang có người hướng dẫn chuyển khoản này — dấu hiệu lừa đảo điển hình."
            ]
            + chk["reasons"],
            "message_for_customer": "Giao dịch được tạm giữ để bảo vệ bạn. Ngân hàng, công an, FinVay KHÔNG BAO GIỜ hướng dẫn bạn chuyển tiền qua điện thoại hay mạng xã hội.",
        }
    chk = {**chk, "risk_score": ai.risk_score(chk["decision"], chk["reasons"])}
    if chk["decision"] == "warn" and (not body.confirm):
        return {**chk, "needs_confirm": True, "context": ctx}

    def notify(transfer_id):
        inbox_add(
            wallet,
            acc["phone"],
            "FinVay",
            "[FinVay] Giao dich chuyen tien cua Quy khach dang duoc TAM GIU de bao ve Quy khach. Neu co nguoi huong dan Quy khach vay roi chuyen tien, do la lua dao. Lien he tong dai chinh thuc trong ung dung.",
            "official",
        )
        where = "trực tiếp từ app" if source == "app" else "(mô phỏng)"
        return live_alert(
            wallet,
            "transfer",
            acc["app_id"],
            f"Tạm giữ giao dịch {body.amount:,} đ {where} — {(chk['reasons'][0] if chk['reasons'] else '')}".replace(
                ",", "."
            ),
            "; ".join(chk["reasons"]),
            "khan",
            0.9 if ctx["ring_case"] else 0.8 if ctx["simo_flag"] or ctx["times_reported"] else 0.65,
            ["shared_recipient"]
            if ctx["ring_case"]
            else ["simo"]
            if ctx["simo_flag"]
            else ["fast_out_stranger"],
            n_reports=ctx["times_reported"],
            transfer_id=transfer_id,
        )

    return writes.transfer(wallet.tools, acc, body, ctx, chk, source, now_iso(), notify)


def register(router, wallet):
    @router.post("/transfer")
    async def transfer(body: TransferIn, request: Request):
        acc = me(wallet, request)
        if body.amount > acc["balance"]:
            raise HTTPException(400, "Số dư không đủ")
        t0 = time.perf_counter()
        ctx = build_ctx(wallet, acc, body)
        chk = await ai_transfer(wallet, ctx)
        return commit_transfer(
            wallet, acc, body, ctx, {**chk, "latency_ms": round((time.perf_counter() - t0) * 1000)}
        )

    @router.get("/transfers")
    def history(request: Request):
        acc = me(wallet, request)
        return wallet.tools.q(
            "SELECT tx_id, ts, to_name, to_bank, to_id, amount, note, decision, status FROM khach_transfers WHERE phone=? ORDER BY tx_id DESC",
            acc["phone"],
        )
