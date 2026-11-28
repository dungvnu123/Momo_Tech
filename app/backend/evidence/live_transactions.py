import json

from app import db


def live_transactions(context, applications):
    if not db.has_table(context.store.db, "khach_transfers"):
        return []
    by_id = {a["app_id"]: a for a in applications}
    rows = context.store.q(
        "SELECT t.*, a.app_id AS application_id, a.full_name AS applicant_name "
        "FROM khach_transfers t JOIN apps a ON a.phone=t.phone "
        "WHERE a.app_id = ANY(?) AND a.applied_at <= ? AND t.ts <= ? ORDER BY t.ts,t.tx_id",
        list(by_id),
        context.cutoff,
        context.cutoff,
    )
    result = []
    for row in rows:
        cursor = context.alert.get("context", {}).get("event_sequence")
        if cursor is not None:
            position = context.store.q(
                "SELECT sequence FROM ai_events WHERE kind='transfer' AND source_id=?",
                "KT" + str(row["tx_id"]),
            )
            if position and position[0]["sequence"] > cursor:
                continue
        app = by_id[row["application_id"]]
        saved = json.loads(row.get("context") or "{}")
        loan_id = row.get("loan_id")
        if loan_id is None and app["loan_id"] is not None:
            # Legacy rows predate explicit binding: resolve at transfer time, never at read time.
            loans = context.store.q(
                "SELECT loan_id FROM khach_loans WHERE phone=? AND disbursed_at<=? "
                "ORDER BY disbursed_at DESC,loan_id DESC LIMIT 1",
                row["phone"],
                row["ts"],
            )
            loan_id = loans[0]["loan_id"] if loans else None
        if loan_id != app["loan_id"]:
            continue
        result.append(
            {
                **row,
                "transfer_id": "KT" + str(row["tx_id"]),
                "created_at": row["ts"],
                "from_wallet": row["phone"],
                "loan_amount": app["amount"],
                "disbursed_at": app["disbursed_at"],
                "loan_id": loan_id,
                "source_table": "khach_transfers",
                "stored_context": saved,
                "simo_flag": saved.get("simo_flag"),
                "recipient_in_contacts": saved.get("recipient_in_contacts"),
                "prior_transfers_to_recipient": saved.get("prior_transfers_to_recipient"),
                "contact_saved_minutes_ago": saved.get("contact_saved_minutes_ago"),
                "coached": saved.get("coached", False),
            }
        )
    return result
