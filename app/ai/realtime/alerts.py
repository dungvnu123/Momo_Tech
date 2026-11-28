import hashlib
import json


def snapshot(store, event, ids, *, truncated=False):
    cluster_id = "RT" + hashlib.sha256("|".join(ids).encode()).hexdigest()[:24]
    alert_id = (
        event["payload"].get("alert_id")
        or "RA" + hashlib.sha256(event["event_id"].encode()).hexdigest()[:24]
    )
    loans = {}
    for app in store.apps(ids):
        rows = store.q(
            "SELECT loan_id FROM khach_loans l WHERE phone=? AND disbursed_at<=? "
            "AND NOT EXISTS (SELECT 1 FROM ai_events e WHERE e.kind='loan' AND e.source_id='KL'||l.loan_id::text AND e.sequence>?) "
            "ORDER BY disbursed_at DESC,loan_id DESC LIMIT 1",
            app["phone"],
            event["occurred_at"],
            event["sequence"],
        )
        loans[app["app_id"]] = rows[0]["loan_id"] if rows else None
    if event["kind"] == "transfer":
        row = store.q("SELECT loan_id FROM khach_transfers WHERE tx_id=?", event["source_id"][2:])[
            0
        ]
        loans[event["app_id"]] = row["loan_id"]
    elif event["kind"] == "loan":
        loans[event["app_id"]] = int(event["source_id"][2:])
    context = json.dumps(
        {
            "loan_ids": loans,
            "event_id": event["event_id"],
            "event_sequence": event["sequence"],
            "scope_truncated": truncated,
        }
    )
    with store.transaction():
        store.run(
            "INSERT INTO alerts (alert_id,ts,day,kind,cid,transfer_id,title,reason,severity,priority,confidence,size,n_pending,n_reports,"
            "suspected_type,signals,app_ids,latest,context) VALUES (?,?,?,?,?,?,?,?,'tb',10,0,?,0,0,'realtime','[]',?,TRUE,?) "
            "ON CONFLICT (alert_id) DO NOTHING",
            alert_id,
            event["occurred_at"],
            event["occurred_at"][:10],
            "transfer" if event["kind"] == "transfer" else "cluster",
            cluster_id,
            event["source_id"] if event["kind"] == "transfer" else None,
            "Dữ liệu mới cần sàng lọc AI",
            "Đang đối chiếu bằng chứng, chưa xác định vai trò",
            len(ids),
            json.dumps(ids),
            context,
        )
        store.run(
            "UPDATE alerts SET cid=?,app_ids=?,size=?,context=? WHERE alert_id=?",
            cluster_id,
            json.dumps(ids),
            len(ids),
            context,
            alert_id,
        )
    return store.alert(alert_id)
