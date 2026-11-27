


def timeline(store, request, views):
    fields = {"app_id", "applied_at", "disbursed_at", "status", "dpd"}
    rows = [store.application(identifier.removeprefix("app:")) for identifier in request.app_ids]
    return {"app_ids": [row["app_id"] for row in rows],
            "applications": [{key: value for key, value in row.items() if key in fields}
                             for row in sorted(rows, key=lambda row: (row["applied_at"], row["app_id"]))]}
