import re
from .constants import MODE,NOTE_TAGS
from .indicators import plain
def note_tags(note) -> list[str]:
    """Phân loại nội dung chuyển khoản thành nhãn — gửi nhãn cho AI thay vì chữ khách gõ (không lộ dữ liệu riêng)."""
    text = plain(note or '')
    return [tag for tag, pattern in NOTE_TAGS.items() if re.search(f'(?i){pattern}', text)]

def check_transfer(ctx: dict) -> dict:
    """ctx: amount, loan_amount, minutes_after_disbursal, to_name_matches_borrower, recipient_in_contacts,
    contact_saved_minutes_ago, prior_transfers_to_recipient, simo_flag, to_wallet_age_days, note, times_reported."""
    reasons = []
    ring = ctx.get('ring_case')
    if ring:
        reasons.append(f"Tài khoản nhận thuộc đường dây {ring['cid']} đang bị điều tra — đã nhận tiền từ {ring['n_senders']} hồ sơ vay khác.")
    if ctx.get('simo_flag'):
        reasons.append('Tài khoản nhận nằm trong danh sách nghi gian lận của hệ thống SIMO (NHNN).')
    if ctx.get('times_reported'):
        reasons.append(f"Tài khoản nhận đã bị {ctx['times_reported']} người báo lừa đảo.")
    fresh_loan = ctx.get('minutes_after_disbursal', 1000000000.0) <= 120 and ctx['amount'] >= 0.8 * max(ctx.get('loan_amount') or 1, 1)
    stranger = not ctx.get('to_name_matches_borrower')
    unknown = ctx.get('prior_transfers_to_recipient', 0) == 0 and (not ctx.get('recipient_in_contacts') or (ctx.get('contact_saved_minutes_ago') is not None and ctx['contact_saved_minutes_ago'] < 180))
    if fresh_loan and stranger:
        reasons.append('Chuyển gần hết khoản vay vừa giải ngân cho người khác tên.')
    if fresh_loan and stranger and unknown:
        reasons.append('Người nhận không có trong danh bạ (hoặc vừa được lưu vài phút trước) và bạn chưa từng chuyển cho họ.')
    if ctx.get('to_wallet_age_days') not in (None, '') and int(ctx['to_wallet_age_days']) <= 7:
        reasons.append(f"Ví nhận mới mở {ctx['to_wallet_age_days']} ngày.")
    tags = note_tags(ctx.get('note'))
    if 'fee' in tags:
        reasons.append("Nội dung chuyển khoản giống kịch bản 'phí giải ngân / xác minh'.")
    known = ctx.get('prior_transfers_to_recipient', 0) > 0 and ctx.get('recipient_in_contacts') and ((ctx.get('contact_saved_minutes_ago') or 0) >= 1440)
    if known and (not (ring or ctx.get('simo_flag') or ctx.get('times_reported'))):
        return {'decision': 'allow', 'reasons': [f"Người nhận quen: đã chuyển {ctx['prior_transfers_to_recipient']} lần, có trong danh bạ từ lâu."], 'message_for_customer': '', 'mode': MODE}
    fake_collect = 'debt_collection' in tags and unknown
    if fake_collect:
        reasons.append('Nội dung là trả nợ/tất toán nhưng người nhận là tài khoản cá nhân — FinVay chỉ thu nợ trong ứng dụng.')
    bal = ctx.get('balance')
    big_new = bal is not None and stranger and unknown and (ctx['amount'] >= max(0.5 * bal, 2000000))
    if big_new and (not fresh_loan):
        reasons.append('Chuyển phần lớn số dư cho người lạ lần đầu.')
    if 'urgent' in tags and unknown:
        reasons.append('Nội dung mang tính thúc giục/khẩn cấp — chiêu thường gặp khi mạo danh người thân.')
    hard = ring or ctx.get('simo_flag') or ctx.get('times_reported') or fake_collect
    decision = 'hold' if hard or (fresh_loan and stranger and unknown and (len(reasons) >= 3)) else 'warn' if fresh_loan and stranger or big_new else 'allow'
    msg = {'hold': 'Giao dịch đang được tạm giữ để bảo vệ bạn. FinVay chỉ thu nợ trong ứng dụng, KHÔNG BAO GIỜ yêu cầu chuyển vào tài khoản cá nhân.' if fake_collect else 'Giao dịch đang được tạm giữ để bảo vệ bạn. FinVay KHÔNG BAO GIỜ thu phí giải ngân hay phí xác minh. Nếu ai đó hướng dẫn bạn vay rồi chuyển tiền, đó là lừa đảo.', 'warn': 'Bạn sắp chuyển phần lớn số dư cho người chưa từng giao dịch. Nếu là người thân nhắn qua mạng xã hội, hãy GỌI ĐIỆN xác minh trước.' if big_new and (not fresh_loan) else 'Bạn sắp chuyển gần hết khoản vay vừa nhận cho người lạ. Hãy chắc chắn bạn biết người nhận.', 'allow': ''}[decision]
    return {'decision': decision, 'reasons': reasons, 'message_for_customer': msg, 'mode': MODE}

def risk_score(decision: str, reasons: list) -> int:
    """Điểm rủi ro 0–100 để hiển thị: dải theo quyết định, trong dải tăng theo số lý do."""
    lo, hi = {'allow': (2, 30), 'warn': (45, 75), 'hold': (80, 99)}[decision]
    return min(hi, lo + 6 * len(reasons))
