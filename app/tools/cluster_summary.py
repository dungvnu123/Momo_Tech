"""Deterministic cluster-wide money statistics with bounded source records."""


def summarize_money(applications, transfers, reports, *, cluster_id=None, limit=20, offset=0, coverage=None):
    if not 1 <= len(applications) <= 100:
        raise ValueError("Expected 1..100 applications")
    apps = {}
    for row in applications:
        identifier = row["app_id"]
        if identifier in apps:
            raise ValueError("Duplicate application")
        apps[identifier] = {
            "app_id": identifier, "record_id": row["record_id"], "loan_amount": int(row["amount"]),
            "transfer_count": 0, "total_amount": 0, "rapid_stranger_amount": 0,
            "same_name_amount": 0, "unknown_name_amount": 0, "simo_transfer_count": 0,
            "transfer_ids": [], "report_ids": [], "victim_self_report_count": 0,
            "held_transfer_count": 0, "held_amount": 0,
        }
    rows = sorted(transfers, key=lambda t: (t.get("created_at") or "", t["transfer_id"]))
    if len({row["transfer_id"] for row in rows}) != len(rows):
        raise ValueError("Ambiguous or duplicate transfer attribution")
    recipients = {}
    for row in rows:
        app = apps[row["app_id"]]
        amount = int(row["amount"])
        if row.get("status", "done") != "done":
            app["held_transfer_count"] += 1
            app["held_amount"] += amount
            continue
        app["transfer_count"] += 1
        app["total_amount"] += amount
        app["transfer_ids"].append(row["transfer_id"])
        app["simo_transfer_count"] += row.get("simo_flag") is True
        matches, minutes = row.get("recipient_name_matches_applicant"), row.get("minutes_after_disbursal")
        if matches is True:
            app["same_name_amount"] += amount
        elif matches is None:
            app["unknown_name_amount"] += amount
        if matches is False and minutes is not None and 0 <= minutes <= 120:
            app["rapid_stranger_amount"] += amount
        recipient = recipients.setdefault(row["recipient_node_id"], {
            "node_id": row["recipient_node_id"], "sender_app_ids": set(), "amount": 0,
            "transfer_count": 0, "transfer_ids": [], "record_ids": [], "report_ids": set(),
            "simo_transfer_count": 0, "identity_resolved": row.get("recipient_resolved", True),
        })
        recipient["sender_app_ids"].add(row["app_id"])
        recipient["amount"] += amount
        recipient["transfer_count"] += 1
        recipient["transfer_ids"].append(row["transfer_id"])
        recipient["record_ids"].append(row["record_id"])
        recipient["simo_transfer_count"] += row.get("simo_flag") is True
    for report in reports:
        reporters = set(report.get("reporter_app_ids", []))
        related = reporters & apps.keys()
        for node in report.get("matched_recipient_node_ids", []):
            recipient = recipients.get(node)
            if recipient:
                recipient["report_ids"].add(report["report_id"])
                related.update(recipient["sender_app_ids"])
        report["related_app_ids"] = sorted(related)
        for app_id in related:
            apps[app_id]["report_ids"].append(report["report_id"])
        if report.get("reporter_is_victim"):
            for app_id in reporters & apps.keys():
                apps[app_id]["victim_self_report_count"] += 1
    app_summaries = []
    for app in apps.values():
        app["rapid_stranger_ratio"] = round(app["rapid_stranger_amount"] / max(app["loan_amount"], 1), 4)
        app["ids_truncated"] = len(app["transfer_ids"]) > 20 or len(app["report_ids"]) > 20
        app["transfer_ids"] = app["transfer_ids"][:20]
        app["report_ids"] = sorted(set(app["report_ids"]))[:20]
        app_summaries.append(app)
    recipient_rows = []
    for r in sorted(recipients.values(), key=lambda r: (-len(r["sender_app_ids"]), -r["amount"], r["node_id"])):
        recipient_rows.append({**r, "sender_app_ids": sorted(r["sender_app_ids"]),
            "sender_count": len(r["sender_app_ids"]), "transfer_ids": r["transfer_ids"][:20],
            "record_ids": r["record_ids"][:20], "report_ids": sorted(r["report_ids"])[:20],
            "ids_truncated": len(r["transfer_ids"]) > 20 or len(r["report_ids"]) > 20})
    return {
        "cluster_id": cluster_id, "app_ids": list(apps), "application_count": len(apps),
        "totals": {"loan_amount": sum(a["loan_amount"] for a in apps.values()),
                   "transfer_count": sum(a["transfer_count"] for a in apps.values()), "transfer_amount": sum(a["total_amount"] for a in apps.values()),
                   "held_transfer_count": sum(a["held_transfer_count"] for a in apps.values()),
                   "held_amount": sum(a["held_amount"] for a in apps.values()),
                   "rapid_stranger_applications": sum(a["loan_amount"] > 0 and a["rapid_stranger_amount"] * 5 >= 4 * a["loan_amount"] for a in apps.values()),
                   "shared_recipient_count": sum(len(r["sender_app_ids"]) > 1 for r in recipients.values()),
                   "simo_transfer_count": sum(a["simo_transfer_count"] for a in apps.values())},
        "application_summaries": app_summaries, "recipients": recipient_rows[:20],
        "recipient_count": len(recipient_rows), "recipients_truncated": len(recipient_rows) > 20,
        "transfers": rows[offset:offset + limit], "reports": reports[:50],
        "truncated": offset + limit < len(rows), "next_offset": offset + limit if offset + limit < len(rows) else None,
        "coverage": {**(coverage or {}), "aggregates_cover_all_scope_transfers": True,
                     "transfer_evidence_returned": len(rows[offset:offset + limit]), "report_count": len(reports),
                     "report_evidence_truncated": len(reports) > 50},
        "limitations": ["Name matching is not ownership verification; shared recipients do not establish borrower roles.",
                         "Counts cover this explicit application scope; evidence pages and report analysis may be incomplete."],
    }
