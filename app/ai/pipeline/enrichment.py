from app.graph.ai_store import AIStore
from app.ai.entities.candidates import entity_candidates

from .reports import analyze_stored_reports


async def reports(service, database, report_ids):
    processed, errors = [], []
    for report_id in report_ids:
        try:
            result = await analyze_stored_reports(service, database, [report_id])
            processed.append({"report_id": report_id, "verdict": result[0]["verdict"],
                              "reporter_is_victim": result[0]["reporter_is_victim"]})
        except Exception as error:
            errors.append({"report_id": report_id, "error": type(error).__name__})
    with AIStore(database, read_only=True) as store:
        coverage = store.report_coverage()
    return {"processed": processed, "errors": errors, "coverage": coverage}


async def entities(service, database, groups, limit):
    if not limit:
        return {"pairs": 0, "decisions": [], "skipped": True}
    with AIStore(database) as store:
        ids = sorted({identifier for group in groups for identifier in group["app_ids"]})
        pairs = entity_candidates((store.application(identifier) for identifier in ids), limit=limit)
        if not pairs:
            return {"pairs": 0, "decisions": [], "skipped": True}
        output = await service.resolve_entities(pairs)
        store.persist_entities(pairs, output.decisions)
        return {"pairs": len(pairs), "decisions": [item.model_dump() for item in output.decisions]}
