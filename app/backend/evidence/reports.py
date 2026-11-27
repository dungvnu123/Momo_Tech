import json

from .transactions import recipient_key, transaction_rows


def report_views(context):
    wallets = {r["phone"] for r in context.store.apps(sorted(context.readable_ids))}
    recipients = {recipient_key(t) for t in transaction_rows(context)}
    reports = []
    for row in context.store.q("SELECT * FROM reports WHERE reported_at <= ? ORDER BY reported_at,report_id", context.cutoff):
        analysis = json.loads(row["analysis"])
        indicators = analysis["indicators"]
        identifiers = set(indicators["accounts"] + indicators["phones"])
        matched_keys = [key for key in recipients if key[2] in identifiers]
        matched = sorted(context.token(key) for key in matched_keys)
        if not matched and row["reporter_phone"] not in wallets:
            continue
        reporters = context.store.q("SELECT app_id FROM apps WHERE phone=? AND applied_at <= ?",
                                    row["reporter_phone"], context.cutoff)
        reports.append({
            "report_id": row["report_id"], "reported_at": row["reported_at"],
            "source": {"table": "reports", "id": row["report_id"]},
            "verdict": analysis["verdict"], "reporter_is_victim": analysis["reporter_is_victim"],
            "reporter_app_ids": [r["app_id"] for r in reporters],
            "matched_recipient_node_ids": matched,
            "recipient_match_basis": {context.token(key): "identifier_only_bank_unavailable" if key[0] == "bank" else "wallet_identifier"
                                      for key in matched_keys},
            "match_basis": "identifier_only_bank_unavailable" if matched else "reporter_wallet",
            "annotation_mode": analysis.get("mode", "unknown"),
        })
    return reports
