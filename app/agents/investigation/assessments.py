"""Check scope and attribution, without inferring a person's role by rule."""
from .schemas import ApplicationAssessment


def observed_records(data):
    records = {}
    for row in data.get("application_summaries", []):
        records[row["record_id"]] = {row["app_id"]}
    for row in data.get("transfers", []) + ([data["transfer"]] if data.get("transfer") else []):
        if row.get("record_id") and row.get("app_id"):
            records[row["record_id"]] = {row["app_id"]}
    if data.get("loan", {}).get("loan_record_id") and data.get("application", {}).get("app_id"):
        records[data["loan"]["loan_record_id"]] = {data["application"]["app_id"]}
    for row in data.get("reports", []):
        if row.get("record_id"):
            records[row["record_id"]] = set(row.get("related_app_ids", row.get("reporter_app_ids", [])))
    return records


def validate_assessments(case, steps, scope, *, required=False):
    scope = set(scope)
    reads = {s.tool_call_id: s for s in steps if s.result.get("ok") and s.name != "submit_case"}
    aggregates = [s for s in reads.values() if s.name == "cluster_money_flow" and set(s.result["data"]["app_ids"]) == scope]
    if required and (case.cluster_assessment is None or not aggregates):
        raise ValueError("Read cluster_money_flow for the entire requested scope and supply cluster_assessment; keep borrower roles separate")
    if case.cluster_assessment is None and not case.application_assessments:
        return case

    def check(evidence, app_id=None):
        if evidence.source not in reads:
            raise ValueError("Assessment evidence must cite a successful read from this run")
        data = reads[evidence.source].result.get("data", {})
        records = observed_records(data)
        invalid = [record for record in evidence.record_ids if record not in records]
        if invalid:
            raise ValueError(f"record_ids must be copied from the referenced tool result: source={evidence.source}, "
                             f"unknown={invalid[:3]}, available_examples={list(records)[:10]}. "
                             "Use cluster_money_flow as source for its application/transfer/report record_ids. "
                             "Do not attach those IDs to another tool call; a direct application read can be cited without record_ids.")
        if app_id:
            direct = {data.get("app_id"), data.get("application", {}).get("app_id"), data.get("record", {}).get("app_id")}
            attributed = any(app_id in records[record] for record in evidence.record_ids)
            if app_id not in direct and not attributed:
                raise ValueError("Application evidence must reference records attributed to that application, not just cluster membership")

    if case.cluster_assessment:
        for evidence in case.cluster_assessment.evidence:
            check(evidence)
        if required and not any(e.source in {s.tool_call_id for s in aggregates} for e in case.cluster_assessment.evidence):
            raise ValueError("Cluster assessment must cite the full-scope money aggregation")
        incomplete = False
        for step in aggregates:
            data = step.result["data"]
            report_coverage = data.get("coverage", {}).get("report_analysis")
            incomplete |= bool(data.get("truncated") or data.get("recipients_truncated")
                               or data.get("coverage", {}).get("report_evidence_truncated") or data.get("coverage",{}).get("cohort_truncated"))
            incomplete |= not isinstance(report_coverage, dict) or report_coverage.get("complete") is False
        if incomplete:
            if not case.cluster_assessment.limitations:
                raise ValueError("State incomplete report coverage or truncated evidence in cluster limitations")
    protected = set()
    for s in reads.values():
        data = s.result.get("data", {})
        for row in data.get("application_summaries", []):
            if row.get("victim_self_report_count", 0):
                protected.add(row["app_id"])
        for row in data.get("reports", []):
            if row.get("reporter_is_victim"):
                protected.update(row.get("reporter_app_ids", []))
    assessed = {}
    for item in case.application_assessments:
        if item.app_id in assessed or item.app_id not in scope:
            raise ValueError("Application assessments must be unique and within the requested scope")
        if item.role == "suspected_participant" and item.app_id in protected:
            raise ValueError("Victim self-report evidence requires review; do not assign suspected_participant")
        for evidence in item.evidence:
            check(evidence, item.app_id)
        assessed[item.app_id] = item
    if case.application_assessments or required:
        for app_id in sorted(scope - assessed.keys()):
            assessed[app_id] = ApplicationAssessment(app_id=app_id, role="undetermined", assessment_status="not_assessed",
                reason="Phiên này chưa đưa ra đánh giá riêng cho hồ sơ này.",
                missing_information=["Cần xem bằng chứng riêng của hồ sơ trước khi xác định vai trò."])
        if any(assessed[app].role != "suspected_participant" for app in case.members if app in assessed) or not set(case.members) <= assessed.keys():
            raise ValueError("Legacy members must agree with suspected_participant application assessments")
        if any(assessed[app].role != "possible_victim" for app in case.victims if app in assessed) or not set(case.victims) <= assessed.keys():
            raise ValueError("Legacy victims must agree with possible_victim application assessments")
        case.application_assessments = list(assessed.values())
    return case
