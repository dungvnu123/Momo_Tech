from .constants import MODE

def investigate(c: dict, tools, as_of: str | None=None) -> 'iter[dict]':
    """Sinh từng bước {type: step|case, ...}.
    c: ảnh chụp cụm tại lúc cảnh báo {cluster_id, app_ids, wallets, size, signals, n_pending}.
    as_of: chỉ được thấy dữ liệu tới thời điểm này (không nhìn trước tương lai).
    `tools`: tech_profile, money_flow, account_senders, reports_mentioning (backend/store.py).
    Bản giả lập gọi tool theo kịch bản cố định rồi kết luận bằng luật."""
    yield {'type': 'step', 'tool': 'get_cluster', 'thought': 'Xem cụm và các điểm dùng chung.', 'result': f"{c['size']} hồ sơ; tín hiệu: {', '.join((k for k, v in c['signals'].items() if v)) or '—'}"}
    yield {'type': 'step', 'tool': None, 'thought': 'Thử giả thuyết vô hại trước: gia đình, ký túc xá, VPN công ty, đổi SIM, rút về ngân hàng chính chủ.', 'result': ''}
    tp = tools.tech_profile(c['app_ids'])
    yield {'type': 'step', 'tool': 'tech_profile', 'thought': 'Kiểm tra tín hiệu kỹ thuật lúc nộp hồ sơ.', 'result': tp['summary']}
    flows = tools.money_flow(c['app_ids'], as_of)
    yield {'type': 'step', 'tool': 'money_flow', 'thought': 'Tiền sau giải ngân đi đâu?', 'result': flows['summary']}
    reps = tools.reports_mentioning(flows['recipients'], c['wallets'], as_of)
    yield {'type': 'step', 'tool': 'reports_mentioning', 'thought': 'Nơi nhận tiền có bị ai báo lừa đảo không? Có thành viên nào tự kể bị lừa không?', 'result': reps['summary']}
    victims, members = ([], [])
    if reps['self_reported']:
        victims = flows['fast_out_stranger'] or c['app_ids']
        verdict, rtype = ('victims', 'coached_loan_scam')
        actions = [f'Liên hệ hỗ trợ {len(victims)} khách — đây là nạn nhân, không đưa vào danh sách đen, không đòi nợ như kẻ gian', 'Đề nghị ngân hàng phong toả tài khoản nhận đã bị báo']
    elif flows['shared_recipients'] or tp['bad'] or c['signals'].get('ref_hub') or c['signals'].get('device_hub'):
        members = c['app_ids']
        verdict = 'fraud_ring'
        rtype = 'sim_farm_vpn' if tp['bad'].get('ip_block') or tp['bad'].get('emulator') else 'account_takeover' if tp['bad'].get('hooked') or tp['bad'].get('device_new') else 'shared_reference_burst' if c['signals'].get('ref_hub') else 'rented_wallet' if flows['shared_recipients'] else 'synthetic_identity' if c['signals'].get('device_hub') else 'other'
        actions = [f"Tạm dừng giải ngân các hồ sơ đang chờ trong cụm ({c['n_pending']})", 'Đề nghị phong toả các tài khoản gom', 'Đưa thiết bị/SĐT tham chiếu dùng chung vào danh sách theo dõi']
    else:
        verdict, rtype, actions = ('benign', None, ['Không cần xử lý'])
    conf = 0.85 if reps['self_reported'] or flows['shared_recipients'] else 0.7 if verdict == 'fraud_ring' else 0.5
    yield {'type': 'case', 'case': {'cluster_id': c.get('cluster_id'), 'verdict': verdict, 'ring_type': rtype, 'as_of': as_of, 'confidence': conf, 'members': members, 'victims': victims, 'evidence': [tp['summary'], flows['summary'], reps['summary']], 'actions': actions, 'mode': MODE}}
