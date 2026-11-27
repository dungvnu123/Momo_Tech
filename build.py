# path: build.py
"""Dựng thienla.db: nạp dữ liệu, cho BỘ MÁY REALTIME (app/engine.py) chạy qua toàn bộ sự kiện theo đúng thứ tự
thời gian → bảng cảnh báo có dấu thời gian; rồi điều tra trước cảnh báo mới nhất của mỗi cụm (chỉ dùng dữ liệu
tới lúc cảnh báo) → giám khảo xem ngay, không chờ.

Chạy:  uv run python build.py            (đọc data/, ghi thienla.db)
       uv run python build.py --data data_seed7 --db thienla_seed7.db
ground_truth.json KHÔNG được đọc ở đây — chỉ phần chấm điểm (/api/metrics) mới dùng.
"""
import argparse
import csv
import json
import sqlite3
import time
from pathlib import Path

from app import ai
from app.engine import Engine, events
from app.tools import Tools

ROOT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data")
ap.add_argument("--db", default="thienla.db")
args = ap.parse_args()
DATA, DB = ROOT / args.data, ROOT / args.db
t0 = time.time()


def read(name):
    with open(DATA / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


apps, transfers, reports = read("applications.csv"), read("wallet_transfers.csv"), read("scam_reports.csv")
ekyc, schedule, repayments = read("ekyc_sessions.csv"), read("repayment_schedule.csv"), read("repayments.csv")
DATA_END = max(a["applied_at"] for a in apps)[:10] + "T23:59:59"
analysis = {r["report_id"]: ai.analyze_report(r["raw_text"]) for r in reports}

# ── Bộ máy realtime chạy qua mọi sự kiện theo thời gian ─────────────────────────────────
eng = Engine()
ev = events(apps, transfers, reports, repayments, schedule, DATA_END)
for ts, _, kind, d in ev:
    if kind == "apply":
        eng.apply(d, ts)
    elif kind == "transfer":
        eng.transfer(d, ts)
    elif kind == "report":
        eng.report(d, analysis[d["report_id"]], ts)
    elif kind == "repayment":
        eng.repayment(d, ts)
    else:
        eng.due_check(d, ts)
print(f"engine: {len(ev):,} sự kiện → {len(eng.alerts):,} cảnh báo ({time.time() - t0:.1f}s)")

# ── Ghi SQLite ────────────────────────────────────────────────────────────────────────
if DB.exists():
    DB.unlink()
db = sqlite3.connect(DB)
cols = list(apps[0])
db.execute(f"CREATE TABLE apps ({', '.join(c + (' PRIMARY KEY' if c == 'app_id' else '') for c in cols)}, signals)")
db.executemany(f"INSERT INTO apps VALUES ({','.join('?' * (len(cols) + 1))})",
               [[a[c] for c in cols] + [json.dumps(sorted(eng.sig[a['app_id']]))] for a in apps])
tcols = list(transfers[0])
db.execute(f"CREATE TABLE transfers ({', '.join(tcols)})")
db.executemany(f"INSERT INTO transfers VALUES ({','.join('?' * len(tcols))})", [[t[c] for c in tcols] for t in transfers])
db.execute("CREATE TABLE reports (report_id PRIMARY KEY, reported_at, reporter_phone, channel, raw_text, analysis)")
db.executemany("INSERT INTO reports VALUES (?,?,?,?,?,?)",
               [(r["report_id"], r["reported_at"], r["reporter_phone"], r["channel"], r["raw_text"], json.dumps(analysis[r["report_id"]], ensure_ascii=False)) for r in reports])
for name, rows in (("ekyc_sessions", ekyc), ("schedule", schedule), ("repayments", repayments)):
    c = list(rows[0])
    db.execute(f"CREATE TABLE {name} ({', '.join(c)})")
    db.executemany(f"INSERT INTO {name} VALUES ({','.join('?' * len(c))})", [[r[k] for k in c] for r in rows])
acols = ["alert_id", "ts", "day", "kind", "cid", "transfer_id", "title", "reason", "severity", "priority", "confidence",
         "size", "n_pending", "n_reports", "suspected_type", "signals", "app_ids"]
db.execute(f"CREATE TABLE alerts ({', '.join(c + (' PRIMARY KEY' if c == 'alert_id' else '') for c in acols)}, latest, verdict, case_conf)")
latest = {}
for a in eng.alerts:
    if a["cid"]:
        latest[a["cid"]] = a["alert_id"]
db.executemany(f"INSERT INTO alerts VALUES ({','.join('?' * (len(acols) + 3))})",
               [[json.dumps(a[c]) if c in ("signals", "app_ids") else a[c] for c in acols]
                + [1 if (a["cid"] is None or latest[a["cid"]] == a["alert_id"]) else 0, None, None] for a in eng.alerts])
for ix in ("ekyc_sessions(app_id)", "schedule(app_id)", "repayments(app_id)", "transfers(from_wallet)", "transfers(to_id)", "transfers(transfer_id)", "apps(phone)", "alerts(day)", "alerts(cid)"):
    db.execute(f"CREATE INDEX ix_{ix.replace('(', '_').rstrip(')')} ON {ix}")
db.commit()

# ── Điều tra trước cảnh báo mới nhất của mỗi cụm (as_of = lúc cảnh báo) ───────────────────
tools = Tools(DB)
db.execute("CREATE TABLE cases (alert_id PRIMARY KEY, cid, verdict, members, victims, body)")
n_case = 0
for aid in latest.values():
    a = tools.alert(aid)
    case = list(ai.investigate(a, tools, a["ts"]))[-1]["case"]
    db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?)", (aid, a["cid"], case["verdict"], json.dumps(case["members"]),
                                                           json.dumps(case["victims"]), json.dumps(case, ensure_ascii=False)))
    db.execute("UPDATE alerts SET verdict=?, case_conf=? WHERE alert_id=?", (case["verdict"], case["confidence"], aid))
    n_case += 1
meta = {"apps": len(apps), "transfers": len(transfers), "reports": len(reports), "events": len(ev),
        "candidates": sum(1 for x in eng.sig if eng.sig[x]), "clusters": sum(1 for m in eng.members.values() if len(m) >= 2),
        "alerts": len(eng.alerts), "alert_clusters": len(latest), "transfer_holds": sum(a["kind"] == "transfer" for a in eng.alerts),
        "cases": n_case, "fpd_apps": sum("fpd" in s for s in eng.sig.values()),
        "first_day": ev[0][0][:10], "last_day": DATA_END[:10], "ai_mode": ai.MODE}
db.execute("CREATE TABLE meta (k PRIMARY KEY, v)")
db.executemany("INSERT INTO meta VALUES (?,?)", [(k, json.dumps(v)) for k, v in meta.items()])
db.commit()
print(json.dumps(meta, ensure_ascii=False), f"({time.time() - t0:.1f}s)")
