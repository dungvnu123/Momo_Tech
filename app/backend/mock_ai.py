# path: app/backend/mock_ai.py
"""Bản giả lập bằng luật cho build.py và engine.py khi dựng mẫu offline.

Không gọi model, không đọc ground_truth. Các API web gọi AI thật qua
backend/integration.py; giữ module này để tái tạo cảnh báo và kết luận mẫu.
"""
import re
import unicodedata

MODE = "mock"

OFFICIAL = "FinVay"   # thương hiệu hư cấu trong dữ liệu mô phỏng
INJECTION = re.compile(r"(?i)(bo qua moi chi dan|\[system\]|assistant must|ghi chu cho ai)")
SCAM_HINT = re.compile(r"(?i)(chuyen|nop|ck|stk|\btk\b|vi momo|phi kich hoat|giam 50|tat toan|cong an|khoi kien|xac minh|kich hoat)")
VICTIM_HINT = re.compile(r"(?i)(toi bi lua|toi vua vay|toi da mat|nho .* ho tro|mat tien|khong goi duoc|chan lien lac)")
LEGIT_HINT = re.compile(r"(?i)(khong yeu cau chuyen khoan|ma otp cua ban|cam on quy khach da thanh toan)")
URL_RE = re.compile(r"(?i)\b(?:https?://)?((?:[a-z0-9-]+\.)+(?:com|net|top|vn|ly)(?:/[\w-]+)?)")
ACC_RE = re.compile(r"(?<![\w])((?:[0-9oO][ .]?){8,16}[0-9oO])(?![\w])")


def plain(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_number(raw: str) -> str:
    """Chuẩn hoá số viết lách: bỏ khoảng trắng/chấm, o/O → 0. Phần TẤT ĐỊNH — giữ lại kể cả khi dùng AI."""
    return re.sub(r"[ .]", "", raw).replace("o", "0").replace("O", "0")


def extract_indicators(text: str) -> dict:
    nums = [norm_number(m) for m in ACC_RE.findall(text)]
    nums = [n for n in nums if n.isdigit() and 8 <= len(n) <= 16]
    phones = [n for n in nums if len(n) == 10 and n[0] == "0"]
    return {"accounts": [n for n in nums if n not in phones], "phones": phones,
            "urls": [u for u in URL_RE.findall(text) if not u.lower().startswith(OFFICIAL.lower() + ".")]}


# ── 1. Lá chắn: phân tích tin báo ─────────────────────────────────────────────────────
def analyze_report(text: str) -> dict:
    t = plain(text)[:2000]
    ind = extract_indicators(t)
    reasons = []
    if INJECTION.search(t):
        reasons.append("Tin chứa câu tìm cách ra lệnh cho hệ thống kiểm duyệt — dấu hiệu lừa đảo, bị bỏ qua.")
    is_victim = bool(VICTIM_HINT.search(t))
    if LEGIT_HINT.search(t) and not (ind["accounts"] or ind["phones"][1:]) and not INJECTION.search(t):
        verdict, conf = "safe", 0.8
        reasons.append(f"Khớp mẫu tin chính thức của {OFFICIAL}: không yêu cầu chuyển khoản cá nhân.")
    elif (ind["accounts"] or ind["phones"]) and SCAM_HINT.search(t):
        verdict, conf = "scam", 0.85
        reasons.append(f"Yêu cầu chuyển tiền vào tài khoản/ví cá nhân — {OFFICIAL} chỉ thu tiền trong ứng dụng.")
        if ind["urls"]:
            reasons.append("Có đường link lạ, không phải tên miền chính thức.")
    elif SCAM_HINT.search(t):
        verdict, conf = "suspicious", 0.5
        reasons.append("Có lời lẽ giục chuyển tiền nhưng chưa trích được tài khoản.")
    else:
        verdict, conf = "safe", 0.4
        reasons.append("Không thấy dấu hiệu yêu cầu chuyển tiền.")
    advice = ("Không chuyển tiền. Thanh toán chỉ trong ứng dụng FinVay. Nếu đã chuyển, liên hệ ngân hàng để yêu cầu phong toả ngay."
              if verdict != "safe" else "Tin này có vẻ an toàn. Vẫn không cung cấp OTP cho bất kỳ ai.")
    return {"verdict": verdict, "confidence": conf, "reporter_is_victim": is_victim,
            "indicators": ind, "reasons": reasons, "advice": advice, "mode": MODE}


# ── 2. Cảnh báo lúc chuyển tiền ─────────────────────────────────────────────────────────
def check_transfer(ctx: dict) -> dict:
    """ctx: amount, loan_amount, minutes_after_disbursal, to_name_matches_borrower, recipient_in_contacts,
    contact_saved_minutes_ago, prior_transfers_to_recipient, simo_flag, to_wallet_age_days, note, times_reported."""
    reasons = []
    if ctx.get("simo_flag"):
        reasons.append("Tài khoản nhận nằm trong danh sách nghi gian lận của hệ thống SIMO (NHNN).")
    if ctx.get("times_reported"):
        reasons.append(f"Tài khoản nhận đã bị {ctx['times_reported']} người báo lừa đảo.")
    fresh_loan = ctx.get("minutes_after_disbursal", 1e9) <= 120 and ctx["amount"] >= 0.8 * max(ctx.get("loan_amount") or 1, 1)
    stranger = not ctx.get("to_name_matches_borrower")
    unknown = ctx.get("prior_transfers_to_recipient", 0) == 0 and (
        not ctx.get("recipient_in_contacts") or (ctx.get("contact_saved_minutes_ago") or 1e9) < 180)
    if fresh_loan and stranger:
        reasons.append("Chuyển gần hết khoản vay vừa giải ngân cho người khác tên.")
    if fresh_loan and stranger and unknown:
        reasons.append("Người nhận không có trong danh bạ (hoặc vừa được lưu vài phút trước) và bạn chưa từng chuyển cho họ.")
    if ctx.get("to_wallet_age_days") not in (None, "") and int(ctx["to_wallet_age_days"]) <= 7:
        reasons.append(f"Ví nhận mới mở {ctx['to_wallet_age_days']} ngày.")
    if re.search(r"(?i)phi giai ngan|xac minh|bao lanh|hoan tien|kich hoat", plain(ctx.get("note") or "")):
        reasons.append("Nội dung chuyển khoản giống kịch bản 'phí giải ngân / xác minh'.")
    known = ctx.get("prior_transfers_to_recipient", 0) > 0 and ctx.get("recipient_in_contacts") and (ctx.get("contact_saved_minutes_ago") or 0) >= 1440
    if known and not (ctx.get("simo_flag") or ctx.get("times_reported")):
        return {"decision": "allow", "reasons": [f"Người nhận quen: đã chuyển {ctx['prior_transfers_to_recipient']} lần, có trong danh bạ từ lâu."],
                "message_for_customer": "", "mode": MODE}
    hard = ctx.get("simo_flag") or ctx.get("times_reported")
    decision = "hold" if hard or (fresh_loan and stranger and unknown and len(reasons) >= 3) else \
               "warn" if (fresh_loan and stranger) else "allow"
    msg = {"hold": "Giao dịch đang được tạm giữ để bảo vệ bạn. FinVay KHÔNG BAO GIỜ thu phí giải ngân hay phí xác minh. "
                   "Nếu ai đó hướng dẫn bạn vay rồi chuyển tiền, đó là lừa đảo.",
           "warn": "Bạn sắp chuyển gần hết khoản vay vừa nhận cho người lạ. Hãy chắc chắn bạn biết người nhận.",
           "allow": ""}[decision]
    return {"decision": decision, "reasons": reasons, "message_for_customer": msg, "mode": MODE}


# ── 3. Sàng lọc cụm ─────────────────────────────────────────────────────────────────────
def triage_clusters(summaries: list[dict]) -> list[dict]:
    """summaries: [{cluster_id, size, signals:{...}, n_reports, ...}] → [{cluster_id, decision, suspected_type, reason}]"""
    out = []
    for s in summaries:
        sig = s["signals"]
        bad = [k for k in ("ref_hub", "device_hub", "shared_recipient", "fpd_cluster", "ip_block", "sim_block", "emulator", "ekyc", "fast_out_stranger", "simo") if sig.get(k)]
        strong = s["n_reports"] or any(sig.get(k) for k in ("ref_hub", "device_hub", "shared_recipient", "simo"))
        decision = "investigate" if strong or len(bad) >= 2 else "skip"
        conf = min(0.95, 0.3 + 0.1 * len(bad) + 0.15 * min(s["n_reports"], 3))   # giả lập; AI thật trả độ tin cậy riêng
        out.append({"cluster_id": s["cluster_id"], "decision": decision, "confidence": round(conf, 2),
                    "suspected_type": bad[0] if bad else None,
                    "reason": ("Có tin báo lừa đảo liên quan. " if s["n_reports"] else "") +
                              (f"Tổ hợp tín hiệu: {', '.join(bad)}." if bad else "Không có tổ hợp tín hiệu bất thường.")})
    return out


# ── 4. Thám tử: điều tra 1 cụm ─────────────────────────────────────────────────────────
def investigate(c: dict, tools, as_of: str | None = None) -> "iter[dict]":
    """Sinh từng bước {type: step|case, ...}.
    c: ảnh chụp cụm tại lúc cảnh báo {cluster_id, app_ids, wallets, size, signals, n_pending}.
    as_of: chỉ được thấy dữ liệu tới thời điểm này (không nhìn trước tương lai).
    `tools`: tech_profile, money_flow, account_senders, reports_mentioning (backend/store.py).
    Bản giả lập gọi tool theo kịch bản cố định rồi kết luận bằng luật."""
    yield {"type": "step", "tool": "get_cluster", "thought": "Xem cụm và các điểm dùng chung.",
           "result": f"{c['size']} hồ sơ; tín hiệu: {', '.join(k for k, v in c['signals'].items() if v) or '—'}"}
    yield {"type": "step", "tool": None, "thought": "Thử giả thuyết vô hại trước: gia đình, ký túc xá, VPN công ty, đổi SIM, rút về ngân hàng chính chủ.", "result": ""}
    tp = tools.tech_profile(c["app_ids"])
    yield {"type": "step", "tool": "tech_profile", "thought": "Kiểm tra tín hiệu kỹ thuật lúc nộp hồ sơ.", "result": tp["summary"]}
    flows = tools.money_flow(c["app_ids"], as_of)
    yield {"type": "step", "tool": "money_flow", "thought": "Tiền sau giải ngân đi đâu?", "result": flows["summary"]}
    reps = tools.reports_mentioning(flows["recipients"], c["wallets"], as_of)
    yield {"type": "step", "tool": "reports_mentioning", "thought": "Nơi nhận tiền có bị ai báo lừa đảo không? Có thành viên nào tự kể bị lừa không?", "result": reps["summary"]}
    victims, members = [], []
    # Kẻ gian và nạn nhân có dòng tiền GIỐNG HỆT nhau — khác ở chỗ chính thành viên trong cụm có tự kể bị lừa không.
    if reps["self_reported"]:
        victims = flows["fast_out_stranger"] or c["app_ids"]
        verdict, rtype = "victims", "coached_loan_scam"
        actions = [f"Liên hệ hỗ trợ {len(victims)} khách — đây là nạn nhân, không đưa vào danh sách đen, không đòi nợ như kẻ gian",
                   "Đề nghị ngân hàng phong toả tài khoản nhận đã bị báo"]
    elif flows["shared_recipients"] or tp["bad"] or c["signals"].get("ref_hub") or c["signals"].get("device_hub"):
        members = c["app_ids"]
        verdict = "fraud_ring"
        rtype = ("sim_farm_vpn" if tp["bad"].get("ip_block") or tp["bad"].get("emulator")
                 else "account_takeover" if tp["bad"].get("hooked") or tp["bad"].get("device_new")
                 else "shared_reference_burst" if c["signals"].get("ref_hub")
                 else "rented_wallet" if flows["shared_recipients"]
                 else "synthetic_identity" if c["signals"].get("device_hub") else "other")
        actions = [f"Tạm dừng giải ngân các hồ sơ đang chờ trong cụm ({c['n_pending']})", "Đề nghị phong toả các tài khoản gom",
                   "Đưa thiết bị/SĐT tham chiếu dùng chung vào danh sách theo dõi"]
    else:
        verdict, rtype, actions = "benign", None, ["Không cần xử lý"]
    conf = 0.85 if (reps["self_reported"] or flows["shared_recipients"]) else 0.7 if verdict == "fraud_ring" else 0.5
    yield {"type": "case", "case": {"cluster_id": c.get("cluster_id"), "verdict": verdict, "ring_type": rtype, "as_of": as_of,
                                    "confidence": conf, "members": members, "victims": victims,
                                    "evidence": [tp["summary"], flows["summary"], reps["summary"]],
                                    "actions": actions, "mode": MODE}}
