"""Additive PostgreSQL migration; never rebuild the demo data."""

from app import db


def ensure_schema(store):
    if not db.has_table(store.db, "khach_transfers"):
        return False
    with store.transaction():
        store.run("ALTER TABLE khach_loans ADD COLUMN IF NOT EXISTS app_id TEXT")
        store.run("ALTER TABLE khach_transfers ADD COLUMN IF NOT EXISTS app_id TEXT")
        store.run("ALTER TABLE khach_transfers ADD COLUMN IF NOT EXISTS loan_id INTEGER")
        store.run("ALTER TABLE khach_transfers ADD COLUMN IF NOT EXISTS context TEXT DEFAULT '{}'")
        store.run("ALTER TABLE khach_inbox ADD COLUMN IF NOT EXISTS report_id TEXT")
        store.run("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS context TEXT DEFAULT '{}'")
        store.run("""CREATE TABLE IF NOT EXISTS ai_events (
            event_id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT NOT NULL,
            app_id TEXT NOT NULL, occurred_at TEXT NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            available_at TIMESTAMPTZ NOT NULL DEFAULT now(), lease_until TIMESTAMPTZ,
            error_code TEXT, result TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""")
        store.run("CREATE INDEX IF NOT EXISTS ai_events_pending ON ai_events(status, available_at)")
        store.run("ALTER TABLE ai_events ADD COLUMN IF NOT EXISTS sequence BIGSERIAL")
        store.run("CREATE UNIQUE INDEX IF NOT EXISTS ai_events_sequence ON ai_events(sequence)")
        store.run(
            "CREATE INDEX IF NOT EXISTS ai_report_canonical ON reports USING gin ((analysis::jsonb->'canonical_indicators'))"
        )
        columns = db.table_columns(store.db, "apps")
        for column in ("device_id", "ref1_phone", "ref2_phone"):
            if column in columns:
                store.run(f"CREATE INDEX IF NOT EXISTS ai_apps_{column} ON apps({column})")
        store.run("CREATE INDEX IF NOT EXISTS ai_live_loan_time ON khach_loans(phone,disbursed_at)")
        store.run(
            "CREATE INDEX IF NOT EXISTS ai_live_recipient ON khach_transfers(to_type,to_bank,to_id,ts)"
        )
        store.run("""CREATE TABLE IF NOT EXISTS ai_case_recipients (
            alert_id TEXT NOT NULL, recipient_key TEXT NOT NULL, app_ids TEXT NOT NULL,
            assessment TEXT NOT NULL, verification_status TEXT NOT NULL DEFAULT 'unverified',
            mode TEXT NOT NULL, PRIMARY KEY(alert_id, recipient_key)
        )""")
    return True
