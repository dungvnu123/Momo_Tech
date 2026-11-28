from app.graph.ai_store import AIStore
from . import records


def ingest_event(database, event, app, source, *, analysis=None):
    with AIStore(database) as store:
        store.connection.executescript("""
            CREATE TABLE IF NOT EXISTS live_loans(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ingested_events(event_id TEXT PRIMARY KEY);
        """)
        with store.connection:
            # The outbox lease and this transaction make retries idempotent.
            inserted = store.connection.execute(
                "INSERT INTO ingested_events VALUES (?) ON CONFLICT DO NOTHING RETURNING event_id",
                (event["event_id"],),
            ).fetchone()
            if inserted is None:
                return False
            records.application(store, app)
            if event["kind"] == "loan":
                records.loan(store, source, app["app_id"])
            elif event["kind"] == "transfer":
                records.transfer(store, source, app, event.get("sequence"))
            elif event["kind"] == "report":
                records.report(store, source, analysis)
            else:
                raise ValueError("Unknown event kind")
        return True
