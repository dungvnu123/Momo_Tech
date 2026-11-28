def triage_clusters(summaries: list[dict]) -> list[dict]:
    """summaries: [{cluster_id, size, signals:{...}, n_reports, ...}] → [{cluster_id, decision, suspected_type, reason}]"""
    out = []
    for s in summaries:
        sig = s['signals']
        bad = [k for k in ('ref_hub', 'device_hub', 'shared_recipient', 'fpd_cluster', 'ip_block', 'sim_block', 'emulator', 'ekyc', 'fast_out_stranger', 'simo') if sig.get(k)]
        strong = s['n_reports'] or any((sig.get(k) for k in ('ref_hub', 'device_hub', 'shared_recipient', 'simo')))
        decision = 'investigate' if strong or len(bad) >= 2 else 'skip'
        conf = min(0.95, 0.3 + 0.1 * len(bad) + 0.15 * min(s['n_reports'], 3))
        out.append({'cluster_id': s['cluster_id'], 'decision': decision, 'confidence': round(conf, 2), 'suspected_type': bad[0] if bad else None, 'reason': ('Có tin báo lừa đảo liên quan. ' if s['n_reports'] else '') + (f"Tổ hợp tín hiệu: {', '.join(bad)}." if bad else 'Không có tổ hợp tín hiệu bất thường.')})
    return out
