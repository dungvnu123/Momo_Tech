# path: app/khach.py
"""App ví phía KHÁCH (demo): đăng nhập bằng SĐT + PIN, xem ví/khoản vay, hộp tin, báo lừa đảo, nhận khoản vay, chuyển tiền.

Mọi lần chuyển đi qua ai.check_transfer với ngữ cảnh THẬT tại lúc đó (khoản vay vừa nhận, danh bạ + lúc lưu số,
đã từng chuyển chưa, SIMO giả lập, số tin báo đã có). Tạm giữ / báo lừa đảo → ghi cảnh báo vào hàng đợi đội rủi ro ngay.
"""
import json
import os
import time
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import security
from .backend import mock_ai as ai
from .backend.events import wallet as writes
from .backend.events.knowledge import related_case_count, recipient_reports
from .graph.normalize import account as recipient_identity

router = APIRouter(prefix="/api/khach")
tools = None     # backend.store.Tools — gán từ backend/routes.py (dùng chung kết nối)
adapter = None   # backend.integration.BackendAI — AI thật (Gemini); None/chưa cấu hình → luật giả lập
MAX_LOAN = 20_000_000


def now_iso():
    return security.vntime_now().isoformat(timespec="seconds")


def me(request: Request) -> dict:
    phone = security.khach_phone(request.cookies.get(security.KHACH_COOKIE))
    rows = tools.q("SELECT * FROM khach_accounts WHERE phone=?", phone) if phone else []
    if not rows:
        raise HTTPException(401, "Cần đăng nhập ví")
    return rows[0]


def inbox_add(phone, sender, body, kind):
    tools.run("INSERT INTO khach_inbox (phone, ts, sender, body, kind) VALUES (?,?,?,?,?)", phone, now_iso(), sender, body, kind)


def live_alert(kind, app_id, title, reason, severity, confidence, signals, n_reports=0, transfer_id=None):
    """Cảnh báo phát sinh trực tiếp từ app khách → hiện ngay trên hàng đợi đội rủi ro."""
    ts = now_iso()
    alert_id = "LV" + uuid4().hex
    prio = round({"khan": 3, "cao": 2, "tb": 1}[severity] * 10 + confidence * 10 + 1, 2)
    tools.run("INSERT INTO alerts (alert_id, ts, day, kind, cid, transfer_id, title, reason, severity, priority, confidence, size, n_pending, "
              "n_reports, suspected_type, signals, app_ids, latest, verdict, case_conf) VALUES (?,?,?,?,NULL,?,?,?,?,?,?,1,0,?,?,?,?,TRUE,NULL,NULL)",
              alert_id, ts, ts[:10], kind, transfer_id, title, reason, severity, prio, confidence, n_reports, kind,
              json.dumps(signals), json.dumps([app_id]))
    return alert_id


# ── đăng nhập ───────────────────────────────────────────────────────────────────────
class LoginIn(BaseModel):
    phone: str = Field(pattern=r"^0\d{9}$")
    pin: str = Field(pattern=r"^\d{6}$")


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    rows = tools.q("SELECT pin_salt, pin_hash FROM khach_accounts WHERE phone=?", body.phone)
    # cùng 1 thông báo cho "sai SĐT" và "sai PIN" — không cho dò xem SĐT nào có tài khoản
    if not rows or not security.check_pin(body.pin, rows[0]["pin_salt"], rows[0]["pin_hash"]):
        raise HTTPException(401, "SĐT hoặc PIN không đúng")
    response.set_cookie(security.KHACH_COOKIE, security.make_khach_token(body.phone), max_age=security.KHACH_TTL, httponly=True,
                        samesite="strict", secure=request.url.scheme == "https")
    return {"ok": True}


@router.get("/demo")
def demo_accounts():
    """SĐT các tài khoản demo để bấm chọn. PIN chỉ trả ra khi bật DEMO_AUTOFILL (chế độ trình diễn)."""
    rows = tools.q("SELECT phone, display_name, scenario FROM khach_accounts ORDER BY balance")
    pin = os.environ.get("DEMO_PIN", "") if security.DEMO_AUTOFILL else ""
    return [{"phone": r["phone"], "name": r["display_name"], "scenario": r["scenario"], **({"pin": pin} if pin else {})} for r in rows]


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(security.KHACH_COOKIE)
    return {"ok": True}


def current_loan(acc):
    live = tools.q("SELECT loan_id, amount, disbursed_at FROM khach_loans WHERE phone=? ORDER BY loan_id DESC LIMIT 1", acc["phone"])
    if live:
        return {**live[0], "live": True}
    a = tools.apps([acc["app_id"]])[0]
    return {"amount": int(a["amount"]), "disbursed_at": a["disbursed_at"], "live": False}


@router.get("/me")
def profile(request: Request):
    acc = me(request)
    loan = current_loan(acc)
    nxt = tools.q("SELECT term_no, due_date, total_due FROM schedule WHERE app_id=? AND due_date >= ? ORDER BY due_date LIMIT 1",
                  acc["app_id"], now_iso()[:10])
    unread = tools.q("SELECT COUNT(*) AS n FROM khach_inbox WHERE phone=? AND NOT is_read", acc["phone"])[0]["n"]
    contacts = tools.q("SELECT contact_phone, name, saved_at FROM khach_contacts WHERE phone=? ORDER BY saved_at", acc["phone"])
    return {"name": acc["display_name"], "phone": acc["phone"], "balance": acc["balance"], "loan": loan,
            "next_due": nxt[0] if nxt else None, "unread": unread, "contacts": contacts}


# ── hộp tin + báo lừa đảo ─────────────────────────────────────────────────────────────
@router.get("/inbox")
def inbox(request: Request):
    acc = me(request)
    return tools.q("SELECT msg_id, ts, sender, body, kind, is_read, reported_verdict FROM khach_inbox WHERE phone=? ORDER BY ts DESC", acc["phone"])


@router.post("/inbox/{msg_id}/read")
def read_msg(msg_id: int, request: Request):
    acc = me(request)
    tools.run("UPDATE khach_inbox SET is_read=TRUE WHERE msg_id=? AND phone=?", msg_id, acc["phone"])
    return {"ok": True}


def ai_ready() -> bool:
    try:
        adapter.client.ensure_ready()
        return True
    except Exception:
        return False


async def ai_report(text: str, verified: bool) -> dict:
    """Tin từ kênh chính thức đã xác thực → không cần AI. Còn lại: Gemini nếu đã cấu hình, lỗi/chưa có → luật giả lập."""
    if verified or adapter is None or not ai_ready():
        return {**ai.analyze_report(text, sender_verified=verified), "mode": "kênh xác thực" if verified else "luật (chưa cấu hình AI)"}
    try:
        res = await adapter.analyze_report(text)
        return {**res, "mode": "gemini"}
    except Exception:
        return {**ai.analyze_report(text), "mode": "luật (AI lỗi)"}


async def ai_transfer(ctx: dict) -> dict:
    """Gemini quyết định chính; luật chỉ được NÂNG mức (allow < warn < hold), không bao giờ hạ — vì đầu vào của AI
    chưa có nội dung chuyển khoản/số dư (giả thu nợ, phần lớn số dư). Chưa cấu hình/AI lỗi → luật giả lập."""
    rule = ai.check_transfer(ctx)
    if ctx.get("unverified_case_count") and rule["decision"] == "allow":
        rule = {**rule,"decision":"warn","reasons":rule["reasons"]+["Người nhận có liên kết tới vụ việc AI đang nghi vấn, chưa được xác minh."],
                "message_for_customer":"Hãy xác minh người nhận trước khi tiếp tục; liên kết vụ việc chưa chứng minh lừa đảo."}
    if ctx.get("unscoped_report_count") and rule["decision"] == "allow":
        rule={**rule,"decision":"warn","reasons":["Có tin báo cùng dãy số nhưng chưa xác định đúng ngân hàng/loại người nhận."],
              "message_for_customer":"Cần xác minh người nhận; chưa đủ thông tin để kết luận tin báo nói về tài khoản này."}
    if rule["decision"] == "allow" and not ctx.get("ring_case") and not ctx.get("simo_flag") and not ctx.get("times_reported")             and (ctx["prior_transfers_to_recipient"] or ctx["amount"] < 0.3 * max(ctx.get("balance") or 0, 1)):
        return {**rule, "mode": "đường nhanh (không cần AI)"}   # người nhận quen / khoản nhỏ, không tín hiệu → khỏi gọi AI
    if adapter is None or not ai_ready():
        return {**rule, "mode": "luật (chưa cấu hình AI)"}
    try:
        g = await adapter.check_transfer(ctx)
    except Exception:
        return {**rule, "mode": "luật (AI lỗi)"}
    rank = {"allow": 0, "warn": 1, "hold": 2}
    stricter = rank[rule["decision"]] > rank[g["decision"]]
    reasons = list(g["reasons"]) + [r for r in rule["reasons"] if r not in g["reasons"]]
    return {"decision": rule["decision"] if stricter else g["decision"], "reasons": reasons[:6],
            "message_for_customer": rule["message_for_customer"] if stricter else g["message_for_customer"],
            "mode": "gemini + luật nâng mức" if stricter else "gemini"}


@router.post("/report/{msg_id}")
async def report_msg(msg_id: int, request: Request):
    acc = me(request)
    rows = tools.q("SELECT body, kind FROM khach_inbox WHERE msg_id=? AND phone=?", msg_id, acc["phone"])   # chỉ báo tin của chính mình
    if not rows:
        raise HTTPException(404, "Không thấy tin nhắn")
    res = await ai_report(rows[0]["body"], rows[0]["kind"] == "official")
    ind = res["indicators"]
    seen_before = times_reported(ind["accounts"] + ind["phones"])
    def notify():
        acc_txt = ", ".join(ind["accounts"] + ind["phones"] + ind["urls"]) or "—"
        return live_alert("report", acc["app_id"], f"Khách báo lừa đảo qua app — tài khoản {acc_txt}" + (f" (đã bị báo {seen_before} lần)" if seen_before else ""),
                   "; ".join(res["reasons"]), "khan" if seen_before else "cao", 0.85 if seen_before else 0.6,
                   ["user_report"], n_reports=seen_before + 1)
    saved = writes.report(tools, acc, msg_id, rows[0]["body"], res, now_iso(), notify)
    return {**saved, "times_reported": seen_before}


def times_reported(ids):
    from .backend.http.common import times_reported as count
    return count(tools, ids)


# ── nhận khoản vay (demo) ─────────────────────────────────────────────────────────────
class LoanIn(BaseModel):
    amount: int = Field(ge=1_000_000, le=MAX_LOAN)


@router.post("/loan")
def take_loan(body: LoanIn, request: Request):
    acc = me(request)
    ts = now_iso()
    loan_id = writes.loan(tools, acc, body.amount, ts)
    inbox_add(acc["phone"], "FinVay", f"[FinVay] Khoan vay {body.amount:,}d da giai ngan ve vi luc {ts[11:16]}. "
              "FinVay KHONG thu phi giai ngan hay phi xac minh.".replace(",", "."), "official")
    return {"ok": True, "loan_id": loan_id}


# ── chuyển tiền ─────────────────────────────────────────────────────────────────────
class TransferIn(BaseModel):
    to_type: str = Field(pattern=r"^(bank|momo_wallet)$")
    to_id: str = Field(min_length=8, max_length=19)
    to_bank: str = Field(max_length=20)
    to_name: str = Field(min_length=2, max_length=60)
    amount: int = Field(ge=10_000, le=50_000_000)
    note: str = Field(default="", max_length=120)
    save_contact: bool = False      # khách bấm "lưu người nhận vào danh bạ" (kẻ lừa hay bảo làm việc này)
    confirm: bool = False           # đã đọc cảnh báo và vẫn muốn chuyển
    coached: bool = False           # câu hỏi dừng lại: khách trả lời "có người đang hướng dẫn tôi chuyển"


@router.get("/lookup")
def lookup(to_id: str, request: Request, to_type: str = "bank", to_bank: str = ""):
    """Tra cứu người nhận TRƯỚC khi chuyển. Chỉ trả nhãn mức độ — không lộ mã vụ/số hồ sơ đang điều tra."""
    me(request)
    to_id = ai.norm_number(to_id)
    if not to_id.isdigit() or not 8 <= len(to_id) <= 19:
        raise HTTPException(422, "Số tài khoản/ví chỉ gồm 8–19 chữ số")
    n = times_reported([to_id])
    unscoped=n
    related = 0
    if to_bank or to_type == "momo_wallet":
        try:
            related = related_case_count(tools,to_type,to_bank,to_id)
            n,unscoped=recipient_reports(tools,to_type,to_bank,to_id,now_iso())
        except ValueError:
            raise HTTPException(422,"Cần đúng loại người nhận và mã ngân hàng") from None
    labels = [text for on, text in (
        (tools.q("SELECT 1 FROM ring_accounts WHERE to_id=?", to_id), "Liên quan tới đường dây gian lận đang được điều tra"),
        (tools.q("SELECT 1 FROM simo_list WHERE to_id=?", to_id), "Nằm trong danh sách nghi gian lận của hệ thống SIMO (NHNN)"),
        (n, f"Có {n} tin báo liên quan người nhận")) if on]
    if related:
        labels.append("Có liên kết tới vụ việc AI đề nghị kiểm tra; chưa xác minh là lừa đảo")
    if (to_bank or to_type == "momo_wallet") and unscoped:
        labels.append("Có tin báo cùng dãy số nhưng chưa xác định đúng ngân hàng/loại người nhận")
    return {"risky": bool(labels), "labels": labels,"unverified_case_count":related,
            "exact_report_count":n if to_bank or to_type=="momo_wallet" else 0,"unscoped_report_count":unscoped}


@router.post("/transfer")
async def transfer(body: TransferIn, request: Request):
    acc = me(request)
    if body.amount > acc["balance"]:
        raise HTTPException(400, "Số dư không đủ")
    t0 = time.perf_counter()
    ctx = build_ctx(acc, body)
    chk = await ai_transfer(ctx)
    return commit_transfer(acc, body, ctx, {**chk, "latency_ms": round((time.perf_counter() - t0) * 1000)})


def execute_transfer(acc: dict, body: TransferIn, source: str = "app") -> dict:
    """Bản đồng bộ, luật giả lập — cho bộ mô phỏng (app/sim.py; chạy mỗi giây, không gọi AI để tránh tốn chi phí)."""
    t0 = time.perf_counter()
    ctx = build_ctx(acc, body)
    chk = {**ai.check_transfer(ctx), "mode": "luật (mô phỏng)", "latency_ms": round((time.perf_counter() - t0) * 1000)}
    return commit_transfer(acc, body, ctx, chk, source)


def build_ctx(acc: dict, body: TransferIn) -> dict:
    """Ngữ cảnh THẬT tại lúc chuyển. acc cần: phone, app_id, display_name, balance (None = không theo dõi số dư)."""
    to_id = ai.norm_number(body.to_id)
    if not to_id.isdigit():
        raise HTTPException(422, "Số tài khoản/ví chỉ gồm chữ số")
    try:
        recipient_identity(body.to_type,body.to_bank,to_id)
        if not 8 <= len(to_id) <= 19:
            raise ValueError("Invalid length")
    except ValueError:
        raise HTTPException(422,"Cần đúng số tài khoản/ví, loại người nhận và mã ngân hàng") from None
    if body.save_contact:
        tools.run("INSERT INTO khach_contacts VALUES (?,?,?,?) ON CONFLICT (phone, contact_phone) DO NOTHING",
                  acc["phone"], to_id, body.to_name, now_iso())
    loan, now = current_loan(acc), security.vntime_now()
    exact_reports,unscoped_reports=recipient_reports(tools,body.to_type,body.to_bank,to_id,now.isoformat(timespec="seconds"))
    contact = tools.q("SELECT saved_at FROM khach_contacts WHERE phone=? AND contact_phone=?", acc["phone"], to_id)
    prior = tools.q("SELECT COUNT(*) AS n FROM khach_transfers WHERE phone=? AND to_id=? AND status='done'", acc["phone"], to_id)[0]["n"]
    prior += tools.q("SELECT COUNT(*) AS n FROM transfers WHERE from_wallet=? AND to_id=?", acc["phone"], to_id)[0]["n"]
    ctx = {"amount": body.amount, "loan_amount": loan["amount"],
           "loan_id": loan.get("loan_id"),
           "minutes_after_disbursal": round((now - datetime.fromisoformat(loan["disbursed_at"])).total_seconds() / 60),
           "to_name_matches_borrower": ai.plain(body.to_name).upper() == ai.plain(acc["display_name"]).upper(),
           "recipient_in_contacts": bool(contact),
           "contact_saved_minutes_ago": round((now - datetime.fromisoformat(contact[0]["saved_at"])).total_seconds() / 60) if contact else None,
           "prior_transfers_to_recipient": prior,
           "simo_flag": bool(tools.q("SELECT 1 FROM simo_list WHERE to_id=?", to_id)),
           "to_wallet_age_days": None, "note": body.note, "times_reported": exact_reports, "unscoped_report_count":unscoped_reports,"balance": acc.get("balance"),
           "to_id": to_id, "coached": body.coached,
           "unverified_case_count": related_case_count(tools,body.to_type,body.to_bank,to_id),
           "ring_case": (tools.q("SELECT cid, verdict, n_senders FROM ring_accounts WHERE to_id=? ORDER BY n_senders DESC LIMIT 1", to_id)
                         or [None])[0]}
    return ctx


def commit_transfer(acc: dict, body: TransferIn, ctx: dict, chk: dict, source: str = "app") -> dict:
    """Ghi giao dịch theo quyết định; tạm giữ thì sinh cảnh báo cho đội rủi ro."""
    to_id = ctx["to_id"]
    if body.coached:   # khách tự xác nhận đang bị dẫn dắt → tạm giữ, kể cả khi tín hiệu khác chưa đủ
        chk = {**chk, "decision": "hold",
               "reasons": ["Bạn cho biết đang có người hướng dẫn chuyển khoản này — dấu hiệu lừa đảo điển hình."] + chk["reasons"],
               "message_for_customer": "Giao dịch được tạm giữ để bảo vệ bạn. Ngân hàng, công an, FinVay KHÔNG BAO GIỜ hướng dẫn bạn "
                                       "chuyển tiền qua điện thoại hay mạng xã hội."}
    chk = {**chk, "risk_score": ai.risk_score(chk["decision"], chk["reasons"])}
    if chk["decision"] == "warn" and not body.confirm:
        return {**chk, "needs_confirm": True, "context": ctx}
    def notify(transfer_id):
        inbox_add(acc["phone"], "FinVay", "[FinVay] Giao dich chuyen tien cua Quy khach dang duoc TAM GIU de bao ve Quy khach. "
                  "Neu co nguoi huong dan Quy khach vay roi chuyen tien, do la lua dao. Lien he tong dai chinh thuc trong ung dung.", "official")
        where = "trực tiếp từ app" if source == "app" else "(mô phỏng)"
        return live_alert("transfer", acc["app_id"], f"Tạm giữ giao dịch {body.amount:,} đ {where} — {chk['reasons'][0] if chk['reasons'] else ''}".replace(",", "."),
                   "; ".join(chk["reasons"]), "khan", 0.9 if ctx["ring_case"] else 0.8 if (ctx["simo_flag"] or ctx["times_reported"]) else 0.65,
                   ["shared_recipient"] if ctx["ring_case"] else ["simo"] if ctx["simo_flag"] else ["fast_out_stranger"], n_reports=ctx["times_reported"], transfer_id=transfer_id)
    return writes.transfer(tools, acc, body, ctx, chk, source, now_iso(), notify)


@router.get("/transfers")
def history(request: Request):
    acc = me(request)
    return tools.q("SELECT tx_id, ts, to_name, to_bank, to_id, amount, note, decision, status FROM khach_transfers WHERE phone=? ORDER BY tx_id DESC",
                   acc["phone"])


