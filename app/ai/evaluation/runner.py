import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .entities import evaluate_entities
from .investigation import evaluate_investigations
from .metrics import accuracy, select_reports
from .shield import evaluate_reports
from .transfer import evaluate_transfers
from .triage import evaluate_triage


async def evaluate(service, client, database, data_dir, *, report_limit=12, investigation_limit=4):
    if not 1 <= report_limit <= 200 or not 0 <= investigation_limit <= 12:
        raise ValueError("Invalid evaluation limits")
    data_dir = Path(data_dir)
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    with (data_dir / "scam_reports.csv").open(encoding="utf-8-sig", newline="") as file:
        source_report_ids = {row["report_id"] for row in csv.DictReader(file)}
    if not set(select_reports(truth, report_limit)) <= source_report_ids:
        raise ValueError("Evaluation report IDs do not match the source CSV")
    report_cases, selected_count = await evaluate_reports(service, database, truth, report_limit)
    er_cases, entity_persistence = await evaluate_entities(service, database, truth)
    triage_cases, expected_cases = await evaluate_triage(service, database, truth)
    transfer_results = await evaluate_transfers(service)
    investigations = await evaluate_investigations(client, database, data_dir, expected_cases, investigation_limit)
    return {"created_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
            "model": getattr(client, "model", "test"), "scope": "sampled reports, synthetic pairs/transfers and known groups; not end-to-end detection recall",
            "dataset": {"directory": str(data_dir), "selected_reports": selected_count},
            "summary": {"shield": accuracy(report_cases), "entities": accuracy(er_cases),
                        "triage": accuracy(triage_cases), "transfer": accuracy(transfer_results),
                        "investigation": accuracy(investigations)},
            "reports": report_cases, "entities": er_cases, "triage": triage_cases,
            "transfers": transfer_results, "investigations": investigations,
            "entity_persistence": entity_persistence,
            "model_calls": service.runner.model_calls + sum(item["model_turns"] for item in investigations),
            "structured_model_calls": service.runner.model_calls, "cache_hits": service.runner.cache_hits}
