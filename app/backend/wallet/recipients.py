from fastapi import HTTPException, Request
from app.backend import mock_ai as ai
from .runtime import me, now_iso
from app.backend.knowledge.recipients import related_case_count, recipient_reports


def times_reported(wallet, ids):
    from app.backend.http.common import times_reported as count

    return count(wallet.tools, ids)


def register(router, wallet):
    @router.get("/lookup")
    def lookup(to_id: str, request: Request, to_type: str = "bank", to_bank: str = ""):
        """Tra cứu người nhận TRƯỚC khi chuyển. Chỉ trả nhãn mức độ — không lộ mã vụ/số hồ sơ đang điều tra."""
        me(wallet, request)
        to_id = ai.norm_number(to_id)
        if not to_id.isdigit() or not 8 <= len(to_id) <= 19:
            raise HTTPException(422, "Số tài khoản/ví chỉ gồm 8–19 chữ số")
        n = times_reported(wallet, [to_id])
        unscoped = n
        related = 0
        if to_bank or to_type == "momo_wallet":
            try:
                related = related_case_count(wallet.tools, to_type, to_bank, to_id)
                n, unscoped = recipient_reports(wallet.tools, to_type, to_bank, to_id, now_iso())
            except ValueError:
                raise HTTPException(422, "Cần đúng loại người nhận và mã ngân hàng") from None
        labels = [
            text
            for on, text in (
                (
                    wallet.tools.q("SELECT 1 FROM ring_accounts WHERE to_id=?", to_id),
                    "Liên quan tới đường dây gian lận đang được điều tra",
                ),
                (
                    wallet.tools.q("SELECT 1 FROM simo_list WHERE to_id=?", to_id),
                    "Nằm trong danh sách nghi gian lận của hệ thống SIMO (NHNN)",
                ),
                (n, f"Có {n} tin báo liên quan người nhận"),
            )
            if on
        ]
        if related:
            labels.append("Có liên kết tới vụ việc AI đề nghị kiểm tra; chưa xác minh là lừa đảo")
        if (to_bank or to_type == "momo_wallet") and unscoped:
            labels.append(
                "Có tin báo cùng dãy số nhưng chưa xác định đúng ngân hàng/loại người nhận"
            )
        return {
            "risky": bool(labels),
            "labels": labels,
            "unverified_case_count": related,
            "exact_report_count": n if to_bank or to_type == "momo_wallet" else 0,
            "unscoped_report_count": unscoped,
        }
