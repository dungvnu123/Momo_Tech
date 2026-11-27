import re

from ..pipeline import analyze_stored_reports
from ..shield.indicators import canonical_indicator
from ..shield.schemas import Indicator
from .metrics import select_reports


async def evaluate_reports(service, database, truth, report_limit):
    report_ids = select_reports(truth, report_limit)
    report_cases = []
    for report_id in report_ids:
        expected = truth["reports"][report_id]
        try:
            result = (await analyze_stored_reports(service, database, [report_id]))[0]
            wanted = "safe" if expected["label"] == "legit" else "scam"
            victim = expected["label"].startswith("victim_report")
            account = re.sub(r"\D", "", expected.get("account", ""))
            numbers = {canonical_indicator(Indicator.model_validate(item)).rsplit(":", 1)[-1]
                       for item in result["indicators"] if item["kind"] in {"bank_account", "wallet"}}
            report_cases.append({"report_id": report_id, "label": expected["label"], "expected": wanted,
                                 "actual": result["verdict"], "correct": result["verdict"] == wanted,
                                 "victim_correct": result["reporter_is_victim"] == victim,
                                 "has_account": bool(account), "account_correct": account in numbers if account else None})
        except Exception as error:
            report_cases.append({"report_id": report_id, "expected": "safe" if expected["label"] == "legit" else "scam",
                                 "correct": False, "error": type(error).__name__})
    return report_cases, len(report_ids)
