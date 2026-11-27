import json


def times_reported(tools, ids, as_of="9999"):
    """Số tin báo (tới as_of) nhắc tới 1 trong các tài khoản/SĐT. Lọc trong Postgres bằng JSONB + index GIN
    (dựng ở build.py) — không kéo cả bảng tin báo về Python. Gọi thẳng psycopg vì toán tử `?|` trùng dấu `?`."""
    ids = sorted({x for x in ids if x})
    if not ids:
        return 0
    return tools.db.raw.execute(
        "SELECT COUNT(*) FROM reports WHERE reported_at <= %s AND ((analysis::jsonb->'indicators'->'accounts') ?| %s "
        "OR (analysis::jsonb->'indicators'->'phones') ?| %s)", (as_of, ids, ids)).fetchone()[0]


def alert_row(r):
    r = dict(r)
    r["signals"], r["app_ids"] = json.loads(r["signals"]), json.loads(r["app_ids"])
    r["conf"] = r["case_conf"] if r["case_conf"] is not None else r["confidence"]
    return r
