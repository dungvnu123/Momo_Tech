import json
from uuid import uuid4
from .runtime import now_iso


def inbox_add(wallet, phone, sender, body, kind):
    wallet.tools.run(
        "INSERT INTO khach_inbox (phone, ts, sender, body, kind) VALUES (?,?,?,?,?)",
        phone,
        now_iso(),
        sender,
        body,
        kind,
    )


def live_alert(
    wallet,
    kind,
    app_id,
    title,
    reason,
    severity,
    confidence,
    signals,
    n_reports=0,
    transfer_id=None,
):
    """Cảnh báo phát sinh trực tiếp từ app khách → hiện ngay trên hàng đợi đội rủi ro."""
    ts = now_iso()
    alert_id = "LV" + uuid4().hex
    prio = round({"khan": 3, "cao": 2, "tb": 1}[severity] * 10 + confidence * 10 + 1, 2)
    wallet.tools.run(
        "INSERT INTO alerts (alert_id, ts, day, kind, cid, transfer_id, title, reason, severity, priority, confidence, size, n_pending, n_reports, suspected_type, signals, app_ids, latest, verdict, case_conf) VALUES (?,?,?,?,NULL,?,?,?,?,?,?,1,0,?,?,?,?,TRUE,NULL,NULL)",
        alert_id,
        ts,
        ts[:10],
        kind,
        transfer_id,
        title,
        reason,
        severity,
        prio,
        confidence,
        n_reports,
        kind,
        json.dumps(signals),
        json.dumps([app_id]),
    )
    return alert_id
