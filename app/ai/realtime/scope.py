"""Bounded indexed graph traversal through shared relations, at the event cutoff."""

from app.graph.ai_store import AIStore


def related_applications(database, app_id, cutoff, *, limit=100, sequence=None):
    ids, truncated = {app_id}, False
    with AIStore(database, read_only=True) as graph:
        causal = (
            " AND (payload::jsonb->>'event_sequence' IS NULL OR (payload::jsonb->>'event_sequence')::bigint<=?) "
            if sequence is not None
            else " "
        )
        extra = (sequence,) if sequence is not None else ()
        targets = graph.connection.execute(
            "SELECT target FROM edges WHERE source=? AND observed_at<=? "
            "AND kind IN ('USES_DEVICE','REFERENCE','FROM_IP','SIM_IN','SENT_TO','TRANSFER_ATTEMPT') "
            + causal
            + "ORDER BY id LIMIT 51",
            ("app:" + app_id, cutoff, *extra),
        ).fetchall()
        truncated |= len(targets) > 50
        for target in targets[:50]:
            rows = graph.connection.execute(
                "SELECT DISTINCT source FROM edges WHERE target=? AND observed_at<=? "
                "AND kind IN ('USES_DEVICE','REFERENCE','FROM_IP','SIM_IN','SENT_TO','TRANSFER_ATTEMPT') "
                + causal
                + "ORDER BY source LIMIT 101",
                (target[0], cutoff, *extra),
            ).fetchall()
            truncated |= len(rows) > 100
            for row in rows[:100]:
                if row[0].startswith("app:"):
                    ids.add(row[0][4:])
            if len(ids) > limit:
                truncated = True
                ids = {app_id, *sorted(ids - {app_id})[: limit - 1]}
                break
    return sorted(ids), truncated
