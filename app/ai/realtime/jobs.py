"""Short PostgreSQL transactions; leases never hold a DB lock across model calls."""

import json


def claim(store):
    store.run(
        "UPDATE ai_events SET status='failed',error_code='LeaseExpired',lease_until=NULL "
        "WHERE status='running' AND lease_until<now() AND attempts>=3"
    )
    rows = store.q("""WITH candidate AS (
        SELECT event_id FROM ai_events WHERE
        ((status IN ('pending','retry','waiting_for_model') AND available_at<=now())
          OR (status='running' AND lease_until<now())) AND attempts<3
        ORDER BY created_at,event_id FOR UPDATE SKIP LOCKED LIMIT 1
    ) UPDATE ai_events e SET status='running',lease_until=now()+interval '5 minutes',attempts=attempts+1
      FROM candidate c WHERE e.event_id=c.event_id RETURNING e.*""")
    if not rows:
        return None
    return {**rows[0], "payload": json.loads(rows[0]["payload"])}


def finish(store, event, result):
    store.run(
        "UPDATE ai_events SET status='completed',lease_until=NULL,error_code=NULL,result=? WHERE event_id=?",
        json.dumps(result, ensure_ascii=False),
        event["event_id"],
    )


def fail(store, event, error):
    store.run(
        "UPDATE ai_events SET status=?,lease_until=NULL,error_code=?,available_at=now()+interval '30 seconds' "
        "WHERE event_id=?",
        "failed" if event["attempts"] >= 3 else "retry",
        type(error).__name__,
        event["event_id"],
    )
    if getattr(error, "details", None):
        store.run(
            "UPDATE ai_events SET result=? WHERE event_id=?",
            json.dumps(error.details, ensure_ascii=False),
            event["event_id"],
        )


def wait_for_model(store, event):
    store.run(
        "UPDATE ai_events SET status='waiting_for_model',attempts=attempts-1,lease_until=NULL,"
        "available_at=now()+interval '30 seconds' WHERE event_id=?",
        event["event_id"],
    )
