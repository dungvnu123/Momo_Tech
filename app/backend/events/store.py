"""Durable outbox; callers publish in the business transaction."""

import json


def publish(store, kind, source_id, app_id, occurred_at, *, alert_id=None, simulated=False):
    event_id = f"{kind}:{source_id}"
    store.run(
        "INSERT INTO ai_events (event_id,kind,source_id,app_id,occurred_at,payload) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",
        event_id,
        kind,
        source_id,
        app_id,
        occurred_at,
        json.dumps({"alert_id": alert_id, "simulated": simulated}),
    )
    return event_id
