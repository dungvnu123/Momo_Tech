from ..triage.features import cluster_summary

from app.graph.ai_store import AIStore


async def triage_groups(service, database, groups):
    summaries, decisions = [], []
    with AIStore(database) as store:
        for group in groups:
            summaries.append(cluster_summary(store, group["cluster_id"], group["app_ids"]))
        for start in range(0, len(summaries), 30):
            batch = summaries[start:start + 30]
            result = await service.triage(batch)
            by_id = {item.cluster_id: item for item in result.decisions}
            for summary in batch:
                store.persist_cluster(summary, by_id[summary.cluster_id])
            decisions.extend(result.decisions)
    return summaries, decisions
