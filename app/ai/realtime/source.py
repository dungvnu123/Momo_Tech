import json

from app.ai.shield.schemas import ReportAnalysis


def source_record(store, event):
    table, key, value = {
        "loan": ("khach_loans", "loan_id", event["source_id"][2:]),
        "transfer": ("khach_transfers", "tx_id", event["source_id"][2:]),
        "report": ("reports", "report_id", event["source_id"]),
    }[event["kind"]]
    rows = store.q(f"SELECT * FROM {table} WHERE {key}=?", value)
    if not rows:
        raise ValueError("Event source is unavailable")
    return rows[0]


async def report_analysis(service, client, row):
    saved = json.loads(row["analysis"])
    if saved.get("mode") == "gemini" and saved.get("analysis"):
        return ReportAnalysis.model_validate(saved["analysis"])
    # Mock/error fallback remains evidence in backend, never silently promoted into AI knowledge.
    client.ensure_ready()
    return await service.analyze_report(row["raw_text"][:2000])
