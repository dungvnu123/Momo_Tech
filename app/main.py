# path: app/main.py
"""Web app Thiên La (FastAPI).

Chạy:  uv run python build.py      (1 lần, dựng thienla.db)
       uv run uvicorn app.main:app --port 4420
"""
import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from feature_flow import create_app
from pydantic import BaseModel, Field

from . import ai, security
from .tools import Tools, mask

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / os.environ.get("THIENLA_DB", "thienla.db")
if not DB.exists():
    raise SystemExit(f"Chưa có {DB.name} — chạy: uv run python build.py")
tools = Tools(DB)
app = FastAPI(title="Thiên La", docs_url=None, redoc_url=None, openapi_url=None)   # không lộ sơ đồ API ra ngoài
app.middleware("http")(security.guard)
META = {r["k"]: json.loads(r["v"]) for r in tools.q("SELECT k, v FROM meta")}


# ── Lá chắn ─────────────────────────────────────────────────────────────────────────
class ReportIn(BaseModel):
    text: str = Field(max_length=4000)


class LoginIn(BaseModel):
    password: str = Field(max_length=200)


@app.post("/api/login")
def login(body: LoginIn, request: Request, response: Response):
    if not security.check_password(body.password):
        raise HTTPException(401, "Sai mật khẩu")
    response.set_cookie(security.COOKIE, security.make_token(), max_age=security.TTL, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https" or bool(os.environ.get("THIENLA_BEHIND_PROXY")))
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(security.COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return {"auth_required": bool(security.PASSWORD), "logged_in": security.valid_token(request.cookies.get(security.COOKIE))}


def times_reported(ids):
    ids = set(ids)
    n = 0
    for r in tools.q("SELECT analysis FROM reports"):
        ind = json.loads(r["analysis"])["indicators"]
        n += bool(ids & set(ind["accounts"] + ind["phones"]))
    return n


@app.post("/api/shield/analyze")
def shield(body: ReportIn):
    if not body.text.strip():
        raise HTTPException(400, "Thiếu nội dung tin nhắn")
    res = ai.analyze_report(body.text[:2000])
    ind = res["indicators"]
    res["times_reported"] = times_reported(ind["accounts"] + ind["phones"]) if res["verdict"] != "safe" else 0
    return res


@app.get("/api/shield/samples")
def shield_samples():
    rows = tools.q("SELECT report_id, raw_text, analysis FROM reports ORDER BY report_id")
    pick, seen = [], set()
    for r in rows:   # chọn mẫu đa dạng theo KẾT QUẢ phân tích (không dùng đáp án)
        an = json.loads(r["analysis"])
        key = ("injection" if ai.INJECTION.search(ai.plain(r["raw_text"])) else
               "victim" if an["reporter_is_victim"] else an["verdict"])
        if key not in seen:
            seen.add(key); pick.append({"label": {"scam": "Tin đòi chuyển tiền", "safe": "Tin chính thức", "victim": "Người bị hại kể lại",
                                                  "injection": "Tin có câu lừa AI", "suspicious": "Tin đáng ngờ"}[key], "text": r["raw_text"]})
    return pick


# ── Cảnh báo lúc chuyển tiền ──────────────────────────────────────────────────────────
class TransferIn(BaseModel):
    transfer_id: str = Field(pattern=r"^CK\d{5,8}$")


def transfer_ctx(t):
    a = tools.q("SELECT * FROM apps WHERE phone=?", t["from_wallet"])[0]
    from datetime import datetime
    m = (datetime.fromisoformat(t["created_at"]) - datetime.fromisoformat(a["disbursed_at"])).total_seconds() / 60
    return a, {"amount": int(t["amount"]), "loan_amount": int(a["amount"]), "minutes_after_disbursal": round(m),
               "to_name_matches_borrower": t["to_name"] == ai.plain(a["full_name"]).upper(),
               "recipient_in_contacts": t["recipient_in_contacts"] == "True",
               "contact_saved_minutes_ago": int(t["contact_saved_minutes_ago"]) if t["contact_saved_minutes_ago"] else None,
               "prior_transfers_to_recipient": int(t["prior_transfers_to_recipient"]), "simo_flag": t["simo_flag"] == "True",
               "to_wallet_age_days": t["to_wallet_age_days"], "note": t["note"], "times_reported": times_reported([t["to_id"]])}


@app.get("/api/transfer/samples")
def transfer_samples():
    """Vài giao dịch thật trong dữ liệu, chọn theo TÍN HIỆU (không dùng đáp án) để demo đủ 3 mức."""
    picks = {
        "SIMO gắn cờ": "simo_flag='True'",
        "Người lạ, vừa lưu số": "recipient_in_contacts='True' AND CAST(contact_saved_minutes_ago AS INT) < 120 AND prior_transfers_to_recipient='0' AND to_type='bank'",
        "Ví nhận mới mở": "to_type='momo_wallet' AND CAST(to_wallet_age_days AS INT) <= 7 AND prior_transfers_to_recipient='0'",
        "Trả tiền phòng quen": "note LIKE 'tien phong%' AND CAST(prior_transfers_to_recipient AS INT) > 2 AND recipient_in_contacts='True' AND CAST(contact_saved_minutes_ago AS INT) > 1440",
        "Rút về tài khoản chính chủ": "to_type='bank' AND CAST(prior_transfers_to_recipient AS INT) > 5",
    }
    fresh = lambda c: c["amount"] >= 0.8 * c["loan_amount"] and c["minutes_after_disbursal"] <= 120
    want = {"Trả tiền phòng quen": lambda c: True, "Rút về tài khoản chính chủ": lambda c: c["to_name_matches_borrower"] and fresh(c)}
    out = []
    for label, cond in picks.items():
        for t in tools.q(f"SELECT * FROM transfers WHERE {cond} ORDER BY transfer_id LIMIT 600"):
            a, ctx = transfer_ctx(t)
            if want.get(label, fresh)(ctx):
                out.append({"label": label, "transfer_id": t["transfer_id"], "to_name": t["to_name"], "to_bank": t["to_bank"],
                            "to_id": mask(t["to_id"]), "amount": ctx["amount"], "loan_amount": ctx["loan_amount"],
                            "minutes_after_disbursal": ctx["minutes_after_disbursal"], "note": t["note"]})
                break
    return out


@app.post("/api/transfer/check")
def transfer_check(body: TransferIn):
    rows = tools.q("SELECT * FROM transfers WHERE transfer_id=?", body.transfer_id)
    if not rows:
        raise HTTPException(404, "Không thấy giao dịch")
    _, ctx = transfer_ctx(rows[0])
    return {"context": ctx, **ai.check_transfer(ctx)}


@app.get("/api/overview")
def overview():
    return META


# ── Hàng đợi cảnh báo (Lưới + Thám tử) ────────────────────────────────────────────────
SORTS = {"priority": "priority DESC, ts DESC", "time": "ts DESC", "confidence": "COALESCE(case_conf, confidence) DESC, priority DESC",
         "size": "size DESC, priority DESC"}


def alert_row(r):
    r = dict(r)
    r["signals"], r["app_ids"] = json.loads(r["signals"]), json.loads(r["app_ids"])
    r["conf"] = r["case_conf"] if r["case_conf"] is not None else r["confidence"]
    return r


@app.get("/api/alerts")
def alerts(day: str = "", date_from: str = "", date_to: str = "", severity: str = "", kind: str = "", verdict: str = "",
           min_conf: float = 0, latest: bool = True, q: str = "", sort: str = "priority", limit: int = 200,
           hour_from: int = 0, hour_to: int = 24):
    limit = max(1, min(limit, 500))
    hour_from, hour_to = max(0, min(hour_from, 24)), max(0, min(hour_to, 24))
    where, p = ["1=1"], []
    if hour_from > 0 or hour_to < 24:   # khung giờ trong ngày [hour_from, hour_to)
        where.append("CAST(substr(ts, 12, 2) AS INT) >= ? AND CAST(substr(ts, 12, 2) AS INT) < ?"); p += [hour_from, hour_to]
    if day:
        where.append("day = ?"); p.append(day)
    if date_from:
        where.append("day >= ?"); p.append(date_from)
    if date_to:
        where.append("day <= ?"); p.append(date_to)
    if severity:
        s = severity.split(","); where.append(f"severity IN ({','.join('?' * len(s))})"); p += s
    if kind:
        where.append("kind = ?"); p.append(kind)
    if verdict:
        v = verdict.split(",")
        where.append("(" + " OR ".join("verdict IS NULL" if x == "none" else "verdict = ?" for x in v) + ")")
        p += [x for x in v if x != "none"]
    if min_conf:
        where.append("COALESCE(case_conf, confidence) >= ?"); p.append(min_conf)
    if latest:
        where.append("latest = 1")
    if q:
        where.append("(cid LIKE ? OR app_ids LIKE ? OR title LIKE ?)"); p += [f"%{q}%"] * 3
    w = " AND ".join(where)
    total = tools.q(f"SELECT COUNT(*) n FROM alerts WHERE {w}", *p)[0]["n"]
    rows = tools.q(f"SELECT * FROM alerts WHERE {w} ORDER BY {SORTS.get(sort, SORTS['priority'])} LIMIT ?", *p, limit)
    return {"total": total, "items": [alert_row(r) for r in rows]}


@app.get("/api/alerts/days")
def alert_days():
    return tools.q("SELECT day, COUNT(*) n, SUM(severity='khan') khan, SUM(severity='cao') cao, SUM(severity='tb') tb "
                   "FROM alerts GROUP BY day ORDER BY day")


@app.get("/api/alerts/hours")
def alert_hours(day: str = ""):
    """Số cảnh báo theo giờ trong ngày (0–23); có `day` thì chỉ tính ngày đó."""
    rows = tools.q("SELECT CAST(substr(ts, 12, 2) AS INT) h, COUNT(*) n, SUM(severity='khan') khan, SUM(severity='cao') cao, "
                   "SUM(severity='tb') tb FROM alerts WHERE (? = '' OR day = ?) GROUP BY h", day, day)
    by = {r["h"]: r for r in rows}
    return [by.get(h, {"h": h, "n": 0, "khan": 0, "cao": 0, "tb": 0}) for h in range(24)]


LABEL = {"dev": "Thiết bị", "ref": "SĐT tham chiếu", "ip": "Dải IP", "sim": "Lô SIM", "rcv": "Nơi nhận tiền"}


@app.get("/api/alerts/{aid}")
def alert_detail(aid: str):
    a = tools.alert(aid)
    if not a:
        raise HTTPException(404, "Không thấy cảnh báo")
    hist = tools.q("SELECT alert_id, ts, title, severity FROM alerts WHERE cid=? ORDER BY ts", a["cid"]) if a["cid"] else []
    rows = tools.apps(a["app_ids"])
    nodes, edges, keys = [], [], {}
    for r in rows:
        nodes.append({"data": {"id": r["app_id"], "label": r["app_id"], "kind": "app", "status": r["status"],
                               "name": r["full_name"], "phone": mask(r["phone"]), "amount": int(r["amount"])}})
        ks = [("dev", r["device_id"]), ("ref", r["ref1_phone"]), ("ref", r["ref2_phone"])]
        if r["ip_type"] in ("vpn", "datacenter"):
            ks.append(("ip", r["ip"].rsplit(".", 1)[0] + ".0/24"))
        if int(r["sim_age_days"]) < 30:
            ks.append(("sim", r["phone"][:8] + "xx"))
        for k in ks:
            keys.setdefault(k, set()).add(r["app_id"])
    flows = tools.money_flow(a["app_ids"], a["ts"])
    for to_id, senders in flows["shared_recipients"].items():
        keys[("rcv", to_id)] = set(senders)
    for (kind, val), members in keys.items():
        if len(members) < 2:
            continue
        nid = f"{kind}:{val}"
        nodes.append({"data": {"id": nid, "label": f"{LABEL[kind]}\n{mask(val) if kind in ('ref', 'rcv') else val[-8:]}", "kind": kind}})
        edges += [{"data": {"id": f"{nid}>{m}", "source": m, "target": nid}} for m in members]
    case = tools.q("SELECT body FROM cases WHERE alert_id=?", aid)
    return {"alert": {k: v for k, v in a.items() if k != "wallets"}, "graph": nodes + edges, "money_flow": flows["summary"],
            "history": hist, "case": json.loads(case[0]["body"]) if case else None}


@app.get("/api/apps/{app_id}")
def app_timeline(app_id: str, as_of: str = ""):
    if as_of:
        try:
            __import__("datetime").datetime.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(400, "as_of sai định dạng")
    r = tools.timeline(app_id, as_of or None)
    if not r:
        raise HTTPException(404, "Không thấy hồ sơ")
    return r


@app.get("/api/alerts/{aid}/investigate")
async def investigate(aid: str):
    a = tools.alert(aid)
    if not a:
        raise HTTPException(404, "Không thấy cảnh báo")

    async def stream():
        for ev in ai.investigate(a, tools, a["ts"]):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.6)   # nhịp hiển thị từng bước
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/live")
async def live(start: str = "2026-11-01", day_seconds: float = 12):
    """Phát lại realtime: đồng hồ mô phỏng chạy nhanh (1 ngày = day_seconds giây), đẩy cảnh báo đúng lúc nó sinh ra.
    Cảnh báo do app/engine.py sinh khi xử lý từng sự kiện theo thời gian; chạy thật thì engine đọc thẳng hàng đợi sự kiện."""
    from datetime import datetime, timedelta
    try:
        datetime.fromisoformat(start)
    except ValueError:
        raise HTTPException(400, "Ngày bắt đầu sai định dạng (YYYY-MM-DD)")
    day_seconds = max(1.0, min(day_seconds, 120.0))
    rows = [alert_row(r) for r in tools.q("SELECT * FROM alerts WHERE ts >= ? ORDER BY ts", start)]
    end = datetime.fromisoformat(META["last_day"]) + timedelta(days=1)

    async def stream():
        clock, i, tick = datetime.fromisoformat(start), 0, 0.25
        step = timedelta(days=tick / max(day_seconds, 0.5))
        while clock < end:
            clock += step
            batch = []
            while i < len(rows) and rows[i]["ts"] <= clock.isoformat():
                batch.append(rows[i])
                i += 1
            yield "data: " + json.dumps({"clock": clock.isoformat(timespec="minutes"), "alerts": batch}, ensure_ascii=False) + "\n\n"
            await asyncio.sleep(tick)
        yield "data: " + json.dumps({"clock": end.isoformat(timespec="minutes"), "alerts": [], "done": True}) + "\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


GROUP_NAME = {"A": "Ví thuê/mua", "B": "Tham chiếu chung", "C": "1 người nhiều CCCD", "D": "Trại SIM + VPN", "F": "Chiếm ví + vượt eKYC",
              "G": "Ngủ đông", "E": "Nạn nhân bị dụ vay", "H": "Nạn nhân một-một"}


@app.get("/api/metrics")
def metrics():
    """Chấm so với đáp án — CHỈ để hiển thị đánh giá, không tham gia quyết định."""
    from datetime import datetime
    gt_path = ROOT / os.environ.get("THIENLA_DATA", "data") / "ground_truth.json"
    if not gt_path.exists():
        return {}
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    grp = {x: r["ring"] for r in gt["fraud_rings"] for x in r["app_ids"]}
    grp.update({x: ("E" if v["type"].startswith("coached") else "H") for v in gt["victims"] for x in v["app_ids"]})
    fraud = {x for x, g in grp.items() if g in "ABCDFG"}
    vic = {x for x, g in grp.items() if g in "EH"}
    cand = {r["app_id"] for r in tools.q("SELECT app_id FROM apps WHERE signals != '[]'")}
    cs = tools.q("SELECT members, victims FROM cases")
    mem = {x for c in cs for x in json.loads(c["members"])}
    vv = {x for c in cs for x in json.loads(c["victims"])}
    first_app, first_alert = {}, {}
    for r in tools.apps(list(grp)):
        g = grp[r["app_id"]]
        first_app[g] = min(first_app.get(g, "9999"), r["applied_at"])
    for r in tools.q("SELECT ts, app_ids FROM alerts ORDER BY ts"):
        for x in json.loads(r["app_ids"]):
            if x in grp and grp[x] not in first_alert:
                first_alert[grp[x]] = r["ts"]
    hours = lambda g: round((datetime.fromisoformat(first_alert[g]) - datetime.fromisoformat(first_app[g])).total_seconds() / 3600, 1)
    ttd = [{"group": g, "name": GROUP_NAME[g], "first_seen": first_app[g], "first_alert": first_alert.get(g),
            "hours": hours(g) if g in first_alert else None} for g in "DAEHFGBC"]
    return {"fraud": len(fraud), "victims": len(vic),
            "candidate": {"n": len(cand), "fraud": len(cand & fraud), "victims": len(cand & vic)},
            "cases": {"fraud_flagged": len(mem), "fraud_hit": len(mem & fraud), "victims_as_fraud": len(mem & vic),
                      "benign_as_fraud": len(mem - fraud - vic), "victims_flagged": len(vv), "victims_hit": len(vv & vic)},
            "time_to_alert": ttd, "rules_baseline": {"n": 61306, "fraud": 54, "victims_as_fraud": 21}, "ai_mode": ai.MODE}


app.mount("/flows", create_app(ROOT / "docs" / "flows", can_edit=False, guides=False, title="Thiên La — luồng",
                               home={"url": "/", "label": "← Thiên La"}))
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
