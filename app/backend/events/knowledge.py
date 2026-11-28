import json
from app import db
from app.graph.normalize import account


def related_case_count(store, kind, bank, number):
    if not db.has_table(store.db, "ai_case_recipients"):
        return 0
    key = account(kind, bank, number)
    return store.q(
        "SELECT COUNT(*) AS n FROM ai_case_recipients WHERE recipient_key=? "
        "AND mode='gemini' AND assessment::jsonb->>'level'='suspicious'",
        key,
    )[0]["n"]


def recipient_reports(store, kind, bank, number, as_of):
    key = account(kind, bank, number)
    exact = store.q(
        "SELECT COUNT(*) AS n FROM reports WHERE reported_at<=? AND analysis::jsonb->>'verdict' IN ('scam','suspicious') AND "
        "COALESCE(analysis::jsonb->'canonical_indicators','[]'::jsonb) @> ?::jsonb",
        as_of,
        json.dumps([key]),
    )[0]["n"]
    loose = store.q(
        "SELECT COUNT(*) AS n FROM reports WHERE reported_at<=? AND analysis::jsonb->>'verdict' IN ('scam','suspicious') AND NOT jsonb_exists(analysis::jsonb,'canonical_indicators') "
        "AND (COALESCE(analysis::jsonb->'indicators'->'accounts','[]'::jsonb) @> ?::jsonb "
        "OR COALESCE(analysis::jsonb->'indicators'->'phones','[]'::jsonb) @> ?::jsonb)",
        as_of,
        json.dumps([number]),
        json.dumps([number]),
    )[0]["n"]
    return exact, loose
