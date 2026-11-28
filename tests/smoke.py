"""Kiểm tra hồi quy toàn bộ API (đội rủi ro + app khách) trên server đang chạy.
Chạy: uv run python build.py && (server ở :4420) && python tests/smoke.py .env   — build lại để có dữ liệu demo sạch.
"""
import json
import re
import sys
import urllib.error as E
import urllib.parse as P
import urllib.request as U
import http.cookiejar as C
from pathlib import Path

B = "http://127.0.0.1:4420/"
ENV = dict(l.split("=", 1) for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))
fails = []


def mk():
    return U.build_opener(U.HTTPCookieProcessor(C.CookieJar()))


def call(op, path, body=None, raw=False):
    req = U.Request(B + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"})
    try:
        r = op.open(req)
        data = r.read()
        return r.status, (data.decode() if raw else json.loads(data or b"{}"))
    except E.HTTPError as e:
        data = e.read()
        try:
            return e.code, json.loads(data or b"{}")
        except ValueError:
            return e.code, data.decode()[:200]


def check(name, cond, info=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f" — {info}" if info else ""))
    if not cond:
        fails.append(name)


print("ĐỘI RỦI RO")
op = mk()
check("login đội rủi ro", call(op, "api/login", {"password": ENV["THIENLA_PASSWORD"]})[0] == 200)
st, o = call(op, "api/overview"); check("overview", st == 200 and o["alerts"] > 0, f"{o.get('alerts')} cảnh báo")
st, m = call(op, "api/metrics"); check("metrics", st == 200 and m["cases"]["fraud_hit"] == 58, f"kẻ gian {m.get('cases', {}).get('fraud_hit')}/58")
for q in ["", "severity=khan", "kind=transfer", "verdict=victims", "verdict=none", "min_conf=0.8", "day=2026-11-14", "hour_from=0&hour_to=6",
          "q=C0001", "sort=time", "sort=confidence", "sort=size", "latest=false&limit=600", "date_from=2026-11-01&date_to=2026-11-10"]:
    st, r = call(op, "api/alerts?" + q); check(f"alerts?{q or '(mặc định)'}", st == 200 and "total" in r, f"{r.get('total') if isinstance(r, dict) else r}")
st, d = call(op, "api/alerts/days"); check("alerts/days", st == 200 and len(d) > 50, f"{len(d)} ngày")
st, h = call(op, "api/alerts/hours?day=2026-11-18"); check("alerts/hours", st == 200 and len(h) == 24)
a = call(op, "api/alerts?severity=khan&kind=cluster")[1]["items"][0]
st, det = call(op, "api/alerts/" + a["alert_id"]); check("alert detail + đồ thị", st == 200 and len(det["graph"]) > 0, f"{len(det['graph'])} phần tử, case={det['case'] and det['case']['verdict']}")
st, s = call(op, f"api/alerts/{a['alert_id']}/investigate", raw=True)
ev = [json.loads(l[6:]) for l in s.splitlines() if l.startswith("data:")] if st == 200 else []
check("điều tra (SSE)", st == 200 and ev and ev[-1]["type"] == "case", ev[-1]["case"]["verdict"] if ev else s)
x = a["app_ids"][0]
st, t = call(op, f"api/apps/{x}?as_of={P.quote(a['ts'])}"); check("dòng thời gian hồ sơ", st == 200 and t["events"], f"{len(t['events'])} sự kiện, dob={t['profile']['dob']}")
st, ts = call(op, "api/transfer/samples"); check("transfer/samples", st == 200 and len(ts) >= 3, f"{len(ts)} mẫu")
for smp in ts:
    st, r = call(op, "api/transfer/check", {"transfer_id": smp["transfer_id"]}); check(f"transfer/check {smp['label']}", st == 200, r.get("decision"))
r = op.open(B + "api/live?start=2026-11-14&day_seconds=1"); line = r.readline().decode()
check("live (SSE)", line.startswith("data:"), line[:60])
st, sh = call(mk(), "api/shield/samples"); check("Lá chắn mẫu (công khai)", st == 200 and sh)
st, an = call(mk(), "api/shield/analyze", {"text": sh[0]["text"]}); check("Lá chắn phân tích", st == 200, an.get("verdict"))
check("flows", U.urlopen(B + "flows/").status == 200)

print("APP KHÁCH")
PIN = ENV["DEMO_PIN"]
for i, ph in enumerate(["0881986028", "0740645640", "0927945221"]):
    op = mk()
    check(f"[{i + 1}] login", call(op, "api/khach/login", {"phone": ph, "pin": PIN})[0] == 200)
    me = call(op, "api/khach/me")[1]
    inbox = call(op, "api/khach/inbox")[1]
    scam, scam2 = [m for m in inbox if m["kind"] == "unknown"][:2]
    official = [m for m in inbox if m["kind"] == "official"][0]
    # Tình huống ② (chạy TRƯỚC khi vay, đúng như ngoài đời)
    b2 = re.sub(r"(\d)[ .](?=\d)", r"\1", scam2["body"])
    if i == 0:   # giả bên thu hồi nợ → tạm giữ
        acc2 = max(re.findall(r"\b\d{9,16}\b", b2), key=len)
        st, r = call(op, "api/khach/transfer", {"to_type": "bank", "to_id": acc2, "to_bank": "VCB", "to_name": "CONG TY THU HOI NO AN BINH",
                                                "amount": 1_500_000, "note": "tra no FinVay", "save_contact": False, "confirm": False})
        check(f"[{i + 1}] ② trả 'nợ' vào TK cá nhân → tạm giữ", r.get("status") == "held", f"{r.get('decision')}: {r.get('reasons')}")
    if i == 1:   # link giả + đòi OTP → Lá chắn báo lừa
        rep2 = call(op, f"api/khach/report/{scam2['msg_id']}", {})[1]
        check(f"[{i + 1}] ② link giả đòi OTP → lừa đảo", rep2.get("verdict") == "scam", f"{rep2.get('verdict')}: {rep2.get('reasons')}")
    if i == 2:   # người thân nhờ chuyển gấp → cảnh báo (không chặn cứng: có thể là người thân thật)
        acc2 = max(re.findall(r"\b\d{9,16}\b", b2), key=len)
        st, r = call(op, "api/khach/transfer", {"to_type": "bank", "to_id": acc2, "to_bank": "VIB", "to_name": "NGUYEN VAN BINH",
                                                "amount": 3_000_000, "note": "chuyen gap cho me", "save_contact": False, "confirm": False})
        check(f"[{i + 1}] ② người thân nhờ chuyển gấp → cảnh báo, cần xác nhận", r.get("needs_confirm") is True, f"{r.get('decision')}: {r.get('reasons')}")
        st, r = call(op, "api/khach/transfer", {"to_type": "bank", "to_id": acc2, "to_bank": "VIB", "to_name": "NGUYEN VAN BINH", "amount": 3_000_000,
                                                "note": "chuyen gap cho me", "save_contact": False, "confirm": True, "coached": True})
        check(f"[{i + 1}] ② trả lời 'có người hướng dẫn' → tạm giữ", r.get("status") == "held", f"điểm {r.get('risk_score')}, {r.get('latency_ms')} ms")
    repo = call(op, f"api/khach/report/{official['msg_id']}", {})[1]
    check(f"[{i + 1}] báo nhầm tin CHÍNH THỨC → vẫn ra an toàn", repo.get("verdict") == "safe", repo.get("verdict"))
    me = call(op, "api/khach/me")[1]
    body = re.sub(r"(\d)[ .](?=\d)", r"\1", scam["body"])
    acc = max(re.findall(r"\b\d{9,16}\b", body), key=len)
    name = re.search(r"(?:-|chu tk|\()\s*([A-Z][A-Z ]{4,40}[A-Z])", body).group(1)
    amt = me["loan"]["amount"]
    call(op, "api/khach/loan", {"amount": amt})
    tx = {"to_type": "bank", "to_id": acc, "to_bank": "ACB", "to_name": name, "amount": amt, "note": "xac minh ho so", "save_contact": i == 2, "confirm": False}
    st, r = call(op, "api/khach/transfer", tx)
    check(f"[{i + 1}] {me['name']} chuyển theo tin lừa → tạm giữ", r.get("status") == "held", f"{r.get('decision')}: {r.get('reasons')}")
    me2 = call(op, "api/khach/me")[1]
    check(f"[{i + 1}] tiền chưa rời ví", me2["balance"] == me["balance"] + amt, f"{me['balance']:,} + vay {amt:,} = {me2['balance']:,}")
    rep = call(op, f"api/khach/report/{scam['msg_id']}", {})[1]
    check(f"[{i + 1}] báo tin lừa", rep.get("verdict") == "scam", f"trước đó {rep.get('times_reported')} lượt")
    lk = call(op, f"api/khach/lookup?to_id={acc}")[1]
    check(f"[{i + 1}] tra cứu người nhận vừa bị báo → có nhãn rủi ro", lk.get("risky") is True, lk.get("labels"))
    # giao dịch bình thường: chuyển cho người thân đã lưu từ lâu
    c = me["contacts"][0]
    st, r = call(op, "api/khach/transfer", {"to_type": "momo_wallet", "to_id": c["contact_phone"], "to_bank": "MoMo", "to_name": c["name"].split(" (")[0],
                                            "amount": 200_000, "note": "gui me", "save_contact": False, "confirm": False})
    check(f"[{i + 1}] chuyển 200k cho người thân không bị chặn", r.get("decision") in ("allow",) and r.get("status") == "done", r.get("decision"))

print("PHÂN QUYỀN")
check("khách không xem được hàng đợi", call(mk(), "api/alerts")[0] == 401)
check("chưa đăng nhập không đọc được hộp tin", call(mk(), "api/khach/inbox")[0] == 401)
check("PIN sai", call(mk(), "api/khach/login", {"phone": "0881986028", "pin": "000000"})[0] == 401)
check("cookie khách giả", call(U.build_opener(), "api/khach/me")[0] == 401)
op = mk(); call(op, "api/login", {"password": ENV["THIENLA_PASSWORD"]})
r = call(op, "api/alerts?sort=time&limit=10")[1]["items"]
live = [a for a in r if a["alert_id"].startswith("LV")]
check("cảnh báo từ app khách hiện trên hàng đợi", len(live) >= 8, f"{len(live)} cảnh báo LV mới nhất")
for a in live[:4]:
    print("     ", a["alert_id"], a["ts"][11:16], a["severity"], a["title"][:80])
print(f"\n{'TẤT CẢ ĐẠT' if not fails else 'LỖI: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
