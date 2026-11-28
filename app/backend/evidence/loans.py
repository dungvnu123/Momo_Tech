"""Loan snapshots at the alert time; an explicit transfer binding wins."""

from app import db


def application_at(context, row):
    result = dict(row, loan_id=None, loan_record_id="apps:" + row["app_id"])
    if not db.has_table(context.store.db, "khach_loans"):
        return result
    snapshot = context.alert.get("context", {})
    bindings = snapshot.get("loan_ids", {})
    loan_id = bindings.get(row["app_id"])
    if row["app_id"] in bindings and loan_id is None:
        return result
    condition, params = ("AND loan_id=?", [loan_id]) if loan_id else ("", [])
    cursor = snapshot.get("event_sequence")
    if cursor is not None:
        condition += " AND NOT EXISTS (SELECT 1 FROM ai_events e WHERE e.kind='loan' AND e.source_id='KL'||loan_id::text AND e.sequence>?)"
        params.append(cursor)
    loans = context.store.q(
        "SELECT * FROM khach_loans WHERE phone=? AND disbursed_at <= ? "
        + condition
        + " ORDER BY disbursed_at DESC,loan_id DESC LIMIT 1",
        row["phone"],
        context.cutoff,
        *params,
    )
    if loans:
        loan = loans[0]
        result.update(
            amount=loan["amount"],
            disbursed_at=loan["disbursed_at"],
            loan_id=loan["loan_id"],
            loan_record_id="khach_loans:KL" + str(loan["loan_id"]),
        )
    return result


def applications_at(context, ids):
    return [application_at(context, row) for row in context.store.apps(ids)]
