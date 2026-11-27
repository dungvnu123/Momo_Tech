# path: build.py
"""Dựng PostgreSQL: nạp dữ liệu, cho BỘ MÁY REALTIME (app/engine.py) chạy qua toàn bộ sự kiện theo đúng thứ tự
thời gian → bảng cảnh báo có dấu thời gian; rồi điều tra trước cảnh báo mới nhất của mỗi cụm (chỉ dùng dữ liệu
tới lúc cảnh báo) → giám khảo xem ngay, không chờ.

Chạy:  docker compose up -d db
       uv run python build.py                     (đọc data/, ghi vào DATABASE_URL — XOÁ SẠCH schema public rồi dựng lại)
       uv run python build.py --data data_seed7   (bộ chấm chéo)
ground_truth.json KHÔNG được đọc ở đây — chỉ phần chấm điểm (/api/metrics) mới dùng.
"""
import argparse
import csv
import json
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path

from app import db
from app.backend import mock_ai as ai
from app.engine import Engine, events
from app.security import hash_pin, vntime_now
from app.backend.store import Tools

ROOT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data")
args = ap.parse_args()
DATA = ROOT / args.data
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

# ── Ghi PostgreSQL (COPY hàng loạt) ────────────────────────────────────────────────────
conn = db.connect(autocommit=False)
cur = conn.cursor()
cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")   # build = dựng lại sạch toàn bộ (demo reset)


def load(table, rows, cols, types=None):
    """Bảng thô: mọi cột TEXT (giữ đúng chuỗi như CSV); bảng có `types` thì khai báo kiểu riêng."""
    types = types or {}
    cur.execute(f"CREATE TABLE {table} ({', '.join(f'{c} {types.get(c, "TEXT")}' for c in cols)})")
    with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
        for r in rows:
            cp.write_row(r)


cols = list(apps[0])
load("apps", ([a[c] for c in cols] + [json.dumps(sorted(eng.sig[a["app_id"]]))] for a in apps), cols + ["signals"])
tcols = list(transfers[0])
load("transfers", ([t[c] for c in tcols] for t in transfers), tcols)
load("reports", ((r["report_id"], r["reported_at"], r["reporter_phone"], r["channel"], r["raw_text"],
                  json.dumps(analysis[r["report_id"]], ensure_ascii=False)) for r in reports),
     ["report_id", "reported_at", "reporter_phone", "channel", "raw_text", "analysis"])
for name, rows in (("ekyc_sessions", ekyc), ("schedule", schedule), ("repayments", repayments)):
    c = list(rows[0])
    load(name, ([r[k] for k in c] for r in rows), c)
acols = ["alert_id", "ts", "day", "kind", "cid", "transfer_id", "title", "reason", "severity", "priority", "confidence",
         "size", "n_pending", "n_reports", "suspected_type", "signals", "app_ids"]
latest = {}
for a in eng.alerts:
    if a["cid"]:
        latest[a["cid"]] = a["alert_id"]
load("alerts", ([json.dumps(a[c]) if c in ("signals", "app_ids") else a[c] for c in acols]
                + [a["cid"] is None or latest[a["cid"]] == a["alert_id"], None, None] for a in eng.alerts),
     acols + ["latest", "verdict", "case_conf"],
     {"priority": "REAL", "confidence": "REAL", "case_conf": "REAL", "size": "INT", "n_pending": "INT", "n_reports": "INT", "latest": "BOOLEAN"})
for t, c in (("apps", "app_id"), ("reports", "report_id"), ("alerts", "alert_id")):
    cur.execute(f"ALTER TABLE {t} ADD PRIMARY KEY ({c})")
for ix in ("ekyc_sessions(app_id)", "schedule(app_id)", "repayments(app_id)", "transfers(from_wallet)", "transfers(to_id)",
           "transfers(transfer_id)", "apps(phone)", "alerts(day)", "alerts(cid)", "alerts(ts)", "reports(reporter_phone)"):
    cur.execute(f"CREATE INDEX ON {ix}")
# SIMO giả lập: danh sách tài khoản/ví bị gắn cờ nghi gian lận (bản thật: tra API SIMO của NHNN)
cur.execute("CREATE TABLE simo_list AS SELECT DISTINCT to_id FROM transfers WHERE simo_flag='True'")
cur.execute("ALTER TABLE simo_list ADD PRIMARY KEY (to_id)")
conn.commit()
print(f"postgres: đã nạp ({time.time() - t0:.1f}s)")

# ── Điều tra trước cảnh báo mới nhất của mỗi cụm (as_of = lúc cảnh báo) ───────────────────
tools = Tools(conn)
# Tra "người nhận đã bị báo bao nhiêu lần" mỗi lần chuyển tiền → index GIN trên chỉ báo trong phân tích tin
cur.execute("CREATE INDEX ON reports USING gin ((analysis::jsonb->'indicators'->'accounts'))")
cur.execute("CREATE INDEX ON reports USING gin ((analysis::jsonb->'indicators'->'phones'))")
cur.execute("CREATE TABLE cases (alert_id TEXT PRIMARY KEY, cid TEXT, verdict TEXT, members TEXT, victims TEXT, body TEXT)")
for aid in latest.values():
    a = tools.alert(aid)
    case = list(ai.investigate(a, tools, a["ts"]))[-1]["case"]
    cur.execute("INSERT INTO cases VALUES (%s,%s,%s,%s,%s,%s)", (aid, a["cid"], case["verdict"], json.dumps(case["members"]),
                                                                  json.dumps(case["victims"]), json.dumps(case, ensure_ascii=False)))
    cur.execute("UPDATE alerts SET verdict=%s, case_conf=%s WHERE alert_id=%s", (case["verdict"], case["confidence"], aid))
# Tài khoản nhận của đường dây đã điều tra: nhận tiền (khác tên) từ ≥ 2 hồ sơ trong cùng 1 vụ (thành viên hoặc nạn nhân).
# Lúc khách chuyển tiền, app tra bảng này → nối quyết định thanh toán với kết quả điều tra đường dây.
cur.execute("""
CREATE TABLE ring_accounts AS
SELECT t.to_id, c.cid, c.verdict, COUNT(DISTINCT a.app_id)::int AS n_senders
FROM cases c, jsonb_array_elements_text(c.members::jsonb || c.victims::jsonb) m(app_id)
JOIN apps a ON a.app_id = m.app_id JOIN transfers t ON t.from_wallet = a.phone
WHERE c.verdict <> 'benign' AND t.to_name <> upper(a.full_name)
GROUP BY 1, 2, 3 HAVING COUNT(DISTINCT a.app_id) >= 2""")
cur.execute("CREATE INDEX ON ring_accounts (to_id)")

# ── App khách (demo): tài khoản ví, danh bạ, hộp tin, khoản vay/chuyển tiền trực tiếp ─────────
cur.execute("""
CREATE TABLE khach_accounts (phone TEXT PRIMARY KEY, app_id TEXT, display_name TEXT, pin_salt BYTEA, pin_hash BYTEA,
                             balance BIGINT NOT NULL, created_at TEXT, scenario TEXT);
CREATE TABLE khach_contacts (phone TEXT, contact_phone TEXT, name TEXT, saved_at TEXT, PRIMARY KEY (phone, contact_phone));
CREATE TABLE khach_inbox (msg_id SERIAL PRIMARY KEY, phone TEXT, ts TEXT, sender TEXT, body TEXT, kind TEXT,
                          is_read BOOLEAN DEFAULT FALSE, reported_verdict TEXT);
CREATE TABLE khach_loans (loan_id SERIAL PRIMARY KEY, phone TEXT, amount BIGINT, disbursed_at TEXT);
CREATE TABLE khach_transfers (tx_id SERIAL PRIMARY KEY, phone TEXT, ts TEXT, to_type TEXT, to_id TEXT, to_bank TEXT, to_name TEXT,
                              amount BIGINT, note TEXT, decision TEXT, reasons TEXT, status TEXT);
CREATE INDEX ON khach_inbox (phone); CREATE INDEX ON khach_transfers (phone, to_id);
""")
now = vntime_now()
pin = os.environ.get("DEMO_PIN") or "".join(secrets.choice("0123456789") for _ in range(6))
# Chọn khách demo theo TÍN HIỆU (không dùng đáp án): đã giải ngân trong tháng 11, không có tín hiệu nào, khoản vay vừa phải
demo = [a for a in apps if a["status"] == "DISBURSED" and a["disbursed_at"][:7] == "2026-11" and not eng.sig[a["app_id"]]
        and 5_000_000 <= int(a["amount"]) <= 15_000_000][:3]
# Tài khoản cho tin lừa: 1 tài khoản bị nhiều người báo nhất · 1 tài khoản SIMO đã gắn cờ · 1 tài khoản hoàn toàn mới
hits = {}
for r in reports:
    if analysis[r["report_id"]]["verdict"] == "scam":
        for acc in analysis[r["report_id"]]["indicators"]["accounts"]:
            hits[acc] = hits.get(acc, 0) + 1
reported_acc = max(hits, key=hits.get)
simo_acc = cur.execute("SELECT to_id FROM simo_list WHERE to_id NOT IN (SELECT to_id FROM transfers WHERE to_type='momo_wallet') "
                       "ORDER BY to_id LIMIT 1").fetchone()["to_id"]
fresh_acc = "".join(secrets.choice("0123456789") for _ in range(12))
scams = [
    (reported_acc, "ACB", "NGUYEN THANH TUNG",
     "Ho so cua Quy khach dang bi treo do sai thong tin. De xac minh, vui long vay {amt}d tren ung dung roi chuyen toan bo vao "
     "STK {acc} ngan hang {bank} - {name}. He thong se hoan lai trong 15 phut. Lien he 0889 123 456 neu can ho tro."),
    (simo_acc, "VPB", "TRAN VAN HAU",
     "FINVAY THONG BAO: Quy khach duoc ho tro khoan vay uu dai {amt}d. Sau khi nhan tien, chuyen lai {amt}d vao tk {acc} {bank} "
     "chu tk {name} de kich hoat goi lai suat 0%."),
    (fresh_acc, "TCB", "LE MINH QUAN",
     "Chao ban, minh la nhan vien ho tro khoan vay. Ban vua duoc duyet khoan vay {amt}d, can chuyen lai toan bo vao {bank} {acc} ({name}) "
     "truoc 17h de kich hoat, he thong hoan tra kem tien thuong. Nho luu so tai khoan nay vao danh ba de nhan hoan tien."),
]
fresh2 = "".join(secrets.choice("0123456789") for _ in range(13))
fresh3 = "".join(secrets.choice("0123456789") for _ in range(12))
# Mỗi khách demo: 2 tình huống lừa + tin chính thức. (tình huống, số dư ban đầu, [(phút trước, người gửi, nội dung, loại)])
PERSONAS = [
    ("① Dụ vay rồi chuyển — tài khoản nhận đã bị nhiều người báo · ② Giả bên thu hồi nợ đòi trả vào tài khoản cá nhân", 2_000_000, [
        (7, "+84 9{r}", scams[0][3].format(amt="{amt}", acc=scams[0][0], bank=scams[0][1], name=scams[0][2]), "unknown"),
        (95, "+84 8{r}", "[Thong bao] Phong Thu hoi no FinVay: khoan vay cua Quy khach da qua han 5 ngay. Thanh toan ngay 1.500.000d phi phat cham tra vao "
                         "STK " + fresh2 + " VCB - CONG TY THU HOI NO AN BINH truoc 17h hom nay de tranh bi khoi kien.", "unknown"),
    ]),
    ("① Dụ vay rồi chuyển — tài khoản nhận bị SIMO gắn cờ · ② Link giả “tất toán giảm lãi” đòi mã OTP", 2_500_000, [
        (9, "+84 9{r}", scams[1][3].format(amt="{amt}", acc=scams[1][0], bank=scams[1][1], name=scams[1][2]), "unknown"),
        (40, "FinVay-CSKH", "FinVay: Quy khach duoc GIAM 50% LAI khi tat toan som. Truy cap finvay-tattoan.com va nhap ma OTP vua nhan "
                            "de xac nhan. Uu dai het han sau 2 gio.", "unknown"),
    ]),
    ("① Dụ vay rồi chuyển — tài khoản mới tinh, bị dặn “lưu số vào danh bạ” · ② Người thân nhờ chuyển gấp (Zalo bị chiếm)", 4_500_000, [
        (5, "+84 7{r}", scams[2][3].format(amt="{amt}", acc=scams[2][0], bank=scams[2][1], name=scams[2][2]), "unknown"),
        (25, "Zalo · Mẹ", "Con oi me dang o benh vien, dien thoai sap het pin. Con chuyen gap 3.000.000d vao tk " + fresh3 +
                         " VIB ten NGUYEN VAN BINH (ban cua me) nhe, gap lam, dung goi lai.", "unknown"),
    ]),
]
for i, a in enumerate(demo):
    scenario, balance, scam_msgs = PERSONAS[i]
    salt = secrets.token_bytes(16)
    cur.execute("INSERT INTO khach_accounts VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (a["phone"], a["app_id"], a["full_name"], salt, hash_pin(pin, salt), balance, now.isoformat(timespec="seconds"), scenario))
    for k in ("ref1", "ref2"):   # người thân/bạn bè đã lưu từ lâu
        cur.execute("INSERT INTO khach_contacts VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (a["phone"], a[f"{k}_phone"], f"{a[f'{k}_name']} ({a[f'{k}_relation']})", "2025-01-01T00:00:00"))
    amt = f"{int(a['amount']):,}".replace(",", ".")
    due = cur.execute("SELECT total_due FROM schedule WHERE app_id=%s ORDER BY term_no LIMIT 1", (a["app_id"],)).fetchone()
    due = f"{int(due['total_due']) if due else 1_000_000:,}".replace(",", ".")
    msgs = [(a["disbursed_at"], "FinVay", f"[FinVay] Khoan vay {amt}d cua Quy khach da duoc giai ngan ve vi. Ky thanh toan dau tien xem trong ung dung.", "official"),
            ((now - timedelta(days=1)).isoformat(timespec="seconds"), "FinVay",
             "[FinVay] FinVay KHONG BAO GIO yeu cau chuyen tien vao tai khoan ca nhan hay thu phi giai ngan/xac minh. "
             "Moi khoan thanh toan chi thuc hien trong ung dung. Tuyet doi khong cung cap OTP.", "official")]
    for mins, sender, body, kind in scam_msgs:
        msgs.append(((now - timedelta(minutes=mins)).isoformat(timespec="seconds"), sender.format(r=f"{secrets.randbelow(10**8):08d}"),
                     body.format(amt=amt, due=due), kind))
    for ts, sender, body, kind in msgs:
        cur.execute("INSERT INTO khach_inbox (phone, ts, sender, body, kind) VALUES (%s,%s,%s,%s,%s)", (a["phone"], ts, sender, body, kind))

meta = {"apps": len(apps), "transfers": len(transfers), "reports": len(reports), "events": len(ev),
        "candidates": sum(1 for x in eng.sig if eng.sig[x]), "clusters": sum(1 for m in eng.members.values() if len(m) >= 2),
        "alerts": len(eng.alerts), "alert_clusters": len(latest), "transfer_holds": sum(a["kind"] == "transfer" for a in eng.alerts),
        "cases": len(latest), "fpd_apps": sum("fpd" in s for s in eng.sig.values()),
        "first_day": ev[0][0][:10], "last_day": DATA_END[:10], "ai_mode": ai.MODE}
cur.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
cur.executemany("INSERT INTO meta VALUES (%s,%s)", [(k, json.dumps(v)) for k, v in meta.items()])
conn.commit()
print(json.dumps(meta, ensure_ascii=False), f"({time.time() - t0:.1f}s)")
print("\nTài khoản khách demo (đăng nhập ở /vi/):")
for a in demo:
    print(f"  SĐT {a['phone']} · {a['full_name']}")
if os.environ.get("DEMO_PIN"):
    print("  PIN: lấy từ DEMO_PIN trong .env")
else:
    print(f"  PIN (sinh ngẫu nhiên, đặt DEMO_PIN trong .env để cố định): {pin}")
