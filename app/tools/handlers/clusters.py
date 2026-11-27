from app.ai.triage.features import cluster_summary


def get_cluster(store, request, views):
    record = store.ai_record("ai_clusters", request.cluster_id)
    if record is None:
        raise KeyError(request.cluster_id)
    return {"cluster_id": request.cluster_id, "app_ids": record["summary"]["app_ids"], **record}


def tech_profile(store, request, views):
    ids = [identifier.removeprefix("app:") for identifier in request.app_ids]
    return cluster_summary(store, "technical-profile", ids).model_dump()
