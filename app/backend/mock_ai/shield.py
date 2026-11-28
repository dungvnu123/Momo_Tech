from .constants import MODE,OFFICIAL,INJECTION,SCAM_HINT,VICTIM_HINT,OTP_ASK,LEGIT_HINT
from .indicators import plain,extract_indicators
def analyze_report(text: str, sender_verified: bool=False) -> dict:
    """sender_verified: tin đến từ kênh chính thức đã xác thực (brandname do nhà mạng xác thực) — chỉ app biết, người dán tin thì không."""
    t = plain(text)[:2000]
    ind = extract_indicators(t)
    reasons = []
    if INJECTION.search(t):
        reasons.append('Tin chứa câu tìm cách ra lệnh cho hệ thống kiểm duyệt — dấu hiệu lừa đảo, bị bỏ qua.')
    is_victim = bool(VICTIM_HINT.search(t))
    if sender_verified and (not (ind['accounts'] or ind['urls'])) and (not INJECTION.search(t)):
        verdict, conf = ('safe', 0.95)
        reasons.append(f'Tin đến từ kênh chính thức đã xác thực của {OFFICIAL}, không chứa tài khoản hay đường link lạ.')
    elif LEGIT_HINT.search(t) and (not (ind['accounts'] or ind['phones'][1:])) and (not INJECTION.search(t)):
        verdict, conf = ('safe', 0.8)
        reasons.append(f'Khớp mẫu tin chính thức của {OFFICIAL}: không yêu cầu chuyển khoản cá nhân.')
    elif (ind['accounts'] or ind['phones']) and SCAM_HINT.search(t):
        verdict, conf = ('scam', 0.85)
        reasons.append(f'Yêu cầu chuyển tiền vào tài khoản/ví cá nhân — {OFFICIAL} chỉ thu tiền trong ứng dụng.')
        if ind['urls']:
            reasons.append('Có đường link lạ, không phải tên miền chính thức.')
    elif ind['urls'] and (SCAM_HINT.search(t) or OTP_ASK.search(t)):
        verdict, conf = ('scam', 0.8)
        reasons.append(f"Dẫn tới đường link lạ ({', '.join(ind['urls'])}) — không phải tên miền chính thức của {OFFICIAL}.")
        if OTP_ASK.search(t):
            reasons.append(f'Đòi nhập/cung cấp mã OTP — {OFFICIAL} không bao giờ hỏi OTP.')
    elif SCAM_HINT.search(t):
        verdict, conf = ('suspicious', 0.5)
        reasons.append('Có lời lẽ giục chuyển tiền nhưng chưa trích được tài khoản.')
    else:
        verdict, conf = ('safe', 0.4)
        reasons.append('Không thấy dấu hiệu yêu cầu chuyển tiền.')
    advice = 'Không chuyển tiền. Thanh toán chỉ trong ứng dụng FinVay. Nếu đã chuyển, liên hệ ngân hàng để yêu cầu phong toả ngay.' if verdict != 'safe' else 'Tin này có vẻ an toàn. Vẫn không cung cấp OTP cho bất kỳ ai.'
    return {'verdict': verdict, 'confidence': conf, 'reporter_is_victim': is_victim, 'indicators': ind, 'reasons': reasons, 'advice': advice, 'mode': MODE}
