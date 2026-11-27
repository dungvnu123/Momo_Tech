import json
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from ..store import mask
from .common import alert_row


def register(app, tools, adapter, META):
    SORTS = {"priority": "priority DESC, ts DESC", "time": "ts DESC", "confidence": "COALESCE(case_conf, confidence) DESC, priority DESC",
             "size": "size DESC, priority DESC"}


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
            from datetime import datetime
            try:
                datetime.fromisoformat(as_of)
            except ValueError:
                raise HTTPException(400, "as_of sai định dạng") from None
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
            async for ev in adapter.investigate(a):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")
