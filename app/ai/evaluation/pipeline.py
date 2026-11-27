"""Post-run scoring only: labels are never used to construct the pipeline."""
import json
from pathlib import Path


def score_pipeline(result, truth_file):
    truth = json.loads(Path(truth_file).read_text(encoding="utf-8"))
    fraud, victims = set(), set()
    for group in truth["fraud_rings"]:
        target = victims if group["type"] == "account_takeover_ekyc_bypass" else fraud
        target.update(group["app_ids"])
    victims.update(app for group in truth["victims"] for app in group["app_ids"])
    fraud.update(app for group in truth.get("undetectable", []) for app in group.get("app_ids", []))
    clusters = result.get("clusters", [])
    selected = {app for cluster in result.get("candidates", clusters) for app in cluster["app_ids"]}
    completed = [c for c in clusters if c["status"] == "completed"]
    offenders = {app for c in completed for app in c["case"]["members"]}
    recognized_victims = {app for c in completed for app in c["case"]["victims"]}
    skipped = {app for c in clusters if c["status"] == "skipped_by_triage" for app in c["app_ids"]}
    report_results = result.get("stages", {}).get("reports", {}).get("result", {}).get("processed", [])
    report_scores = []
    for item in report_results:
        expected = truth.get("reports", {}).get(item["report_id"])
        if expected:
            risk = expected["label"] != "legit"
            report_scores.append({"report_id": item["report_id"],
                                  "risk_correct": (item["verdict"] != "safe") == risk,
                                  "victim_flag_correct": item["reporter_is_victim"] == expected["label"].startswith("victim_report")})
    return {
        "scope": "selected_candidates_only; not_full_population_detection_recall; synthetic_new_seed_is_not_real_world_validation",
        "label_policy": "account_takeover_ekyc_bypass treated as victim ownership, consistent with the existing AI evaluation",
        "selected_applications": len(selected), "known_fraud_in_selected_scope": len(fraud & selected),
        "reports_evaluated": len(report_scores), "report_risk_correct": sum(r["risk_correct"] for r in report_scores),
        "report_victim_flag_correct": sum(r["victim_flag_correct"] for r in report_scores),
        "known_victims_in_selected_scope": len(victims & selected),
        "fraud_identified": len(offenders & fraud), "victims_identified": len(recognized_victims & victims),
        "false_offender_flags": len(offenders - fraud), "victims_flagged_as_offenders": len(offenders & victims),
        "known_issue_applications_skipped_by_triage": len(skipped & (fraud | victims)),
        "completed_investigations": len(completed),
        "inconclusive_investigations": sum(c["case"]["verdict"] == "inconclusive" for c in completed),
        "inconclusive_rate": sum(c["case"]["verdict"] == "inconclusive" for c in completed) / len(completed) if completed else None,
        "tool_errors": sum(c.get("failed_tool_calls", 0) for c in clusters),
        "cases_with_evidence": sum(c.get("evidence_count", 0) > 0 for c in completed),
        "invalid_evidence_cases": sum(not c.get("evidence_valid", False) for c in completed),
        "deferred_clusters": sum(c["status"] == "deferred_by_limit" for c in clusters),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "logical_model_calls": result.get("structured_model_calls", 0) + result.get("investigation_model_turns", 0),
    }
