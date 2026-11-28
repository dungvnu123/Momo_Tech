from collections import defaultdict
from datetime import datetime

from app.graph.normalize import name_match
from .loans import applications_at
from .live_transactions import live_transactions


def boolean(value):
    return None if value in (None, "") else str(value).lower() == "true"


def integer(value):
    return None if value in (None, "") else int(value)


def recipient_key(row):
    kind = row["to_type"]
    return kind, row["to_bank"].upper() if kind == "bank" else "", row["to_id"]


def transaction_rows(context, ids=None):
    ids = context.ids if ids is None else ids
    if not ids:
        return []
    applications = applications_at(context, ids)
    original_ids = [a["app_id"] for a in applications if a["loan_id"] is None]
    historical = context.store.q(
        "SELECT t.*, a.app_id AS application_id, a.amount AS loan_amount, "
        "a.disbursed_at, a.full_name AS applicant_name FROM transfers t "
        "JOIN apps a ON a.phone=t.from_wallet WHERE a.app_id = ANY(?) "
        "AND a.applied_at <= ? AND t.created_at <= ? ORDER BY t.created_at,t.transfer_id",
        original_ids, context.cutoff, context.cutoff,
    )
    return sorted(historical + live_transactions(context, applications), key=lambda r: (r["created_at"], r["transfer_id"]))


def transaction_view(context, row, reports):
    key = recipient_key(row)
    node_id = context.token(key)
    disbursed_at = row.get("disbursed_at")
    minutes = ((datetime.fromisoformat(row["created_at"]) - datetime.fromisoformat(disbursed_at)).total_seconds() / 60
               if disbursed_at and disbursed_at <= row["created_at"] else None)
    matches = name_match(row.get("to_name", ""), row.get("applicant_name", ""))
    matching_reports = [r for r in reports if node_id in r["matched_recipient_node_ids"] and r["verdict"] in {"scam", "suspicious"}]
    return {
        "transfer_id": row["transfer_id"], "app_id": row["application_id"],
        "source": {"table": row.get("source_table", "transfers"), "id": row["transfer_id"]},
        "record_id": row.get("source_table", "transfers") + ":" + row["transfer_id"],
        "loan_id": row.get("loan_id"), "status": row.get("status", "done"),
        "customer_says_coached": row.get("coached", False),
        "amount": int(row["amount"]), "loan_amount": int(row["loan_amount"]),
        "created_at": row["created_at"], "minutes_after_disbursal": round(minutes, 2) if minutes is not None else None,
        "transfer_loan_ratio": round(int(row["amount"]) / max(int(row["loan_amount"]), 1), 4),
        "recipient_node_id": node_id, "recipient_type": row["to_type"],
        "recipient_name_matches_applicant": matches, "name_match_is_ownership_verification": False,
        "recipient_in_contacts": boolean(row.get("recipient_in_contacts")),
        "contact_saved_minutes_ago": integer(row.get("contact_saved_minutes_ago")),
        "prior_transfers_to_recipient": integer(row.get("prior_transfers_to_recipient")),
        "recipient_is_merchant": boolean(row.get("to_is_merchant")),
        "recipient_wallet_age_days": integer(row.get("to_wallet_age_days")),
        "simo_flag": boolean(row.get("simo_flag")),
        "reported_recipient_count": len(matching_reports),
        "verified_reported_recipient_count": sum(
            r["annotation_mode"] not in {"mock", "unknown"} and
            r["recipient_match_basis"].get(node_id) in {"wallet_identifier", "bank_qualified_identifier"} for r in matching_reports),
        "report_ids": [r["report_id"] for r in matching_reports],
        "report_match_limitation": "Report identifiers have no bank scope; a bank account-number match needs bank verification.",
    }


def money_flow(context, ids, reports, offset=0, limit=50):
    rows = transaction_rows(context, ids)
    views = [transaction_view(context, row, reports) for row in rows]
    rapid, senders, loans = defaultdict(int), defaultdict(set), {}
    for row in views:
        if row["status"] != "done":
            continue
        loans[row["app_id"]] = row["loan_amount"]
        if row["minutes_after_disbursal"] is not None and 0 <= row["minutes_after_disbursal"] <= 120 and row["recipient_name_matches_applicant"] is False:
            rapid[row["app_id"]] += row["amount"]
            senders[row["recipient_node_id"]].add(row["app_id"])
    fast = sorted(app for app, amount in rapid.items() if amount >= 0.8 * loans[app])
    recipients = sorted({v["recipient_node_id"] for v in views})
    return {
        "app_ids": ids[:100], "fast_out_stranger": fast,
        "summary": f"{len(fast)}/{len(ids)} hồ sơ chuyển ít nhất 80% khoản vay tới người khác tên trong 2 giờ; đây là tín hiệu, chưa xác định vai trò người vay.",
        "recipients": recipients[:50], "recipient_count": len(recipients),
        "shared_recipients": {node: sorted(apps)[:100] for node, apps in senders.items() if len(apps) >= 2},
        "simo_flagged_transfer_ids": [v["transfer_id"] for v in views if v["simo_flag"] is True],
        "transfers": views[offset:offset + limit], "transfer_count": len(views),
        "truncated": offset + limit < len(views),
        "next_offset": offset + limit if offset + limit < len(views) else None,
        "coverage": "Transfers through as_of; aggregates cover all rows, transfer details are paginated.",
    }
