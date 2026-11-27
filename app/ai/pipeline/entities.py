from ..entities.candidates import entity_candidates

from app.graph.ai_store import AIStore


async def resolve_stored_entities(service, database, *, limit=100):
    decisions = []
    with AIStore(database) as store:
        pairs = entity_candidates(store.records("applications"), limit=limit)
        for start in range(0, len(pairs), 20):
            batch = pairs[start:start + 20]
            result = await service.resolve_entities(batch)
            store.persist_entities(batch, result.decisions)
            decisions.extend(result.decisions)
    return decisions
