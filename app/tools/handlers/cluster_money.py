from app.graph.normalize import name_match
from ..cluster_summary import summarize_money
from .common import _app_id


def cluster_money_flow(store, request, views):
    if request.cluster_id:
        record = store.ai_record("ai_clusters", request.cluster_id)
        if record is None:
            raise KeyError(request.cluster_id)
        ids = record["summary"]["app_ids"]
    else:
        ids = [_app_id(value) for value in request.app_ids]
    applications, transfers, recipients = [], [], set()
    for app_id in ids:
        app = store.application(app_id)
        applications.append({"app_id": app_id, "amount": app["amount"], "record_id": "applications:" + app_id})
        for edge in store.application_transfers(app_id):
            attrs = edge["attributes"]
            recipient = views.public_id(edge["target"])
            recipients.add(edge["target"])
            transfers.append({"transfer_id": edge["source_id"], "record_id": "wallet_transfers:" + edge["source_id"],
                "edge_id": edge["id"], "source": {"table": edge["source_table"], "id": edge["source_id"]},
                "app_id": app_id, "recipient_node_id": recipient, "amount": attrs["amount"],
                "created_at": edge["observed_at"], "minutes_after_disbursal": attrs.get("minutes_after_disbursal"),
                "recipient_name_matches_applicant": name_match(app.get("full_name", ""), attrs.get("to_name", "")),
                "simo_flag": attrs.get("simo_flag"), "recipient_resolved": attrs.get("recipient_resolved"),
                "recipient_in_contacts": attrs.get("recipient_in_contacts"),
                "prior_transfers_to_recipient": attrs.get("prior_transfers_to_recipient")})
    report_map = {}
    if store.has_table("ai_report_analysis"):
        for recipient in sorted(recipients):
            for row in store.connection.execute("SELECT * FROM edges WHERE target=? AND kind='MENTIONS' ORDER BY id", (recipient,)):
                analysis = store.ai_record("ai_report_analysis", row["source_id"])
                if analysis is None:
                    continue
                report = report_map.setdefault(row["source_id"], {
                    "report_id": row["source_id"], "record_id": "ai_report_analysis:" + row["source_id"],
                    "source": {"table": "ai_report_analysis", "id": row["source_id"]},
                    "reported_at": row["observed_at"], "verdict": analysis["verdict"],
                    "reporter_is_victim": analysis["reporter_is_victim"],
                    "reporter_app_ids": store.reporter_applications(row["source_id"]),
                    "annotation_mode": "ai", "matched_recipient_node_ids": [],
                })
                report["matched_recipient_node_ids"].append(views.public_id(recipient))
        # Include self-reports even when no extracted indicator matches a recipient.
        for row in store.connection.execute("SELECT id FROM ai_report_analysis ORDER BY id"):
            report_id = row[0]
            if report_id in report_map or not set(store.reporter_applications(report_id)) & set(ids):
                continue
            analysis = store.ai_record("ai_report_analysis", report_id)
            report_map[report_id] = {"report_id": report_id, "record_id": "ai_report_analysis:" + report_id,
                "source": {"table": "ai_report_analysis", "id": report_id}, "verdict": analysis["verdict"],
                "reporter_is_victim": analysis["reporter_is_victim"], "reporter_app_ids": store.reporter_applications(report_id),
                "annotation_mode": "ai", "matched_recipient_node_ids": []}
    return summarize_money(applications, transfers, list(report_map.values()), cluster_id=request.cluster_id,
                           limit=request.limit, offset=request.offset,
                           coverage={"time_scope": "graph_snapshot", "report_analysis": store.report_coverage()})
