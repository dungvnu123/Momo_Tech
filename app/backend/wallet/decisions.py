from app.backend import mock_ai as ai


def ai_ready(wallet) -> bool:
    try:
        wallet.adapter.client.ensure_ready()
        return True
    except Exception:
        return False


async def ai_report(wallet, text: str, verified: bool) -> dict:
    """Tin từ kênh chính thức đã xác thực → không cần AI. Còn lại: Gemini nếu đã cấu hình, lỗi/chưa có → luật giả lập."""
    if verified or wallet.adapter is None or (not ai_ready(wallet)):
        return {
            **ai.analyze_report(text, sender_verified=verified),
            "mode": "kênh xác thực" if verified else "luật (chưa cấu hình AI)",
        }
    try:
        res = await wallet.adapter.analyze_report(text)
        return {**res, "mode": "gemini"}
    except Exception:
        return {**ai.analyze_report(text), "mode": "luật (AI lỗi)"}


async def ai_transfer(wallet, ctx: dict) -> dict:
    """Gemini quyết định chính; luật chỉ được NÂNG mức (allow < warn < hold), không bao giờ hạ — vì đầu vào của AI
    chưa có nội dung chuyển khoản/số dư (giả thu nợ, phần lớn số dư). Chưa cấu hình/AI lỗi → luật giả lập."""
    rule = ai.check_transfer(ctx)
    if ctx.get("unverified_case_count") and rule["decision"] == "allow":
        rule = {
            **rule,
            "decision": "warn",
            "reasons": rule["reasons"]
            + ["Người nhận có liên kết tới vụ việc AI đang nghi vấn, chưa được xác minh."],
            "message_for_customer": "Hãy xác minh người nhận trước khi tiếp tục; liên kết vụ việc chưa chứng minh lừa đảo.",
        }
    if ctx.get("unscoped_report_count") and rule["decision"] == "allow":
        rule = {
            **rule,
            "decision": "warn",
            "reasons": [
                "Có tin báo cùng dãy số nhưng chưa xác định đúng ngân hàng/loại người nhận."
            ],
            "message_for_customer": "Cần xác minh người nhận; chưa đủ thông tin để kết luận tin báo nói về tài khoản này.",
        }
    if (
        rule["decision"] == "allow"
        and (not ctx.get("ring_case"))
        and (not ctx.get("simo_flag"))
        and (not ctx.get("times_reported"))
        and (
            ctx["prior_transfers_to_recipient"]
            or ctx["amount"] < 0.3 * max(ctx.get("balance") or 0, 1)
        )
    ):
        return {**rule, "mode": "đường nhanh (không cần AI)"}
    if wallet.adapter is None or not ai_ready(wallet):
        return {**rule, "mode": "luật (chưa cấu hình AI)"}
    try:
        g = await wallet.adapter.check_transfer(ctx)
    except Exception:
        return {**rule, "mode": "luật (AI lỗi)"}
    rank = {"allow": 0, "warn": 1, "hold": 2}
    stricter = rank[rule["decision"]] > rank[g["decision"]]
    reasons = list(g["reasons"]) + [r for r in rule["reasons"] if r not in g["reasons"]]
    return {
        "decision": rule["decision"] if stricter else g["decision"],
        "reasons": reasons[:6],
        "message_for_customer": rule["message_for_customer"]
        if stricter
        else g["message_for_customer"],
        "mode": "gemini + luật nâng mức" if stricter else "gemini",
    }
