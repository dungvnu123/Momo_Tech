from app.ai.shield.indicators import redact_text


def analysis_view(record):
    return {key: record[key] for key in ("report_id", "verdict", "confidence", "tactics", "reporter_is_victim")
            if key in record}


def reports_mentioning(store, request, views):
    identifier = views.resolve(request.node_id)
    page = store.reports_for_indicator(identifier, limit=request.limit, offset=request.offset)
    reports = []
    for edge in page["edges"]:
        record = store.ai_record("ai_report_analysis", edge["source_id"])
        if record:
            reports.append({**analysis_view(record), "edge_id": edge["id"], "reported_at": edge["observed_at"],
                            "reporter_app_ids": store.reporter_applications(edge["source_id"])})
    return {"node_id": views.public_id(identifier), "reports": reports, "total_reports": page["total_reports"],
            "truncated": page["truncated"], "next_offset": page["next_offset"],
            "analysis_available": store.report_coverage()["indexed"] > 0,
            "analysis_coverage": store.report_coverage()}
