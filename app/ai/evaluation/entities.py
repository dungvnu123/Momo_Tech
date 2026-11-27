from app.graph.ai_store import AIStore

from ..entities.candidates import entity_record
from ..entities.schemas import EntityPair
from .cases import entity_cases


async def evaluate_entities(service, database, truth):
    pairs = entity_cases()
    database_pairs = []
    with AIStore(database) as store:
        identity = next((item for item in truth["fraud_rings"] if item["type"] == "synthetic_identity"), None)
        if identity:
            ids = identity["app_ids"]
            for index, (left, right) in enumerate(zip(ids, ids[1:])):
                pair = EntityPair(pair_id=f"source-pair-{index}", left=entity_record(store.application(left)),
                                  right=entity_record(store.application(right)))
                database_pairs.append(pair)
                pairs.append({"pair": pair.model_dump(), "expected": "same"})
    er_cases = []
    entity_persistence = "not_run"
    try:
        result = await service.resolve_entities([item["pair"] for item in pairs])
        actual = {item.pair_id: item.decision for item in result.decisions}
        er_cases = [{"pair_id": item["pair"]["pair_id"], "expected": item["expected"],
                     "actual": actual[item["pair"]["pair_id"]], "correct": actual[item["pair"]["pair_id"]] == item["expected"]}
                    for item in pairs]
        if database_pairs:
            source_ids = {pair.pair_id for pair in database_pairs}
            try:
                with AIStore(database) as store:
                    store.persist_entities(database_pairs, [item for item in result.decisions if item.pair_id in source_ids])
                entity_persistence = "applied"
            except ValueError:
                entity_persistence = "blocked_inconsistent_merge"
    except Exception as error:
        er_cases = [{"expected": item["expected"], "correct": False, "error": type(error).__name__} for item in pairs]
    return er_cases, entity_persistence
