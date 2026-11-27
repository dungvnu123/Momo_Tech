import json

from app.graph.ai_store import AIStore


async def analyze_stored_reports(service, database, report_ids):
    results = []
    with AIStore(database) as store:
        for report_id in report_ids:
            row = store.connection.execute("SELECT payload FROM scam_reports WHERE id=?", (report_id,)).fetchone()
            if row is None:
                raise KeyError(report_id)
            original = json.loads(row[0])
            result = await service.analyze_report(original["raw_text"])
            store.persist_report(report_id, original["raw_text"], result)
            results.append({"report_id": report_id, **result.model_dump()})
    return results
