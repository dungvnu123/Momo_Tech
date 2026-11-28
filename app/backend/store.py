# path: app/backend/store.py
"""Tool trên PostgreSQL (schema public) — agent Thám tử (giả lập hay Gemini) đều gọi qua đây.
Mọi CCCD/SĐT trả ra đều đã che bớt (mask)."""
import json
import threading
from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime

from app import db

from . import mock_ai as ai


def mask(s: str) -> str:
    s = str(s or "")
    return s[:3] + "****" + s[-3:] if len(s) >= 8 else s


class Tools:
    def __init__(self, database="thienla.db"):
        # database: đường dẫn kiểu cũ (→ schema public) hoặc 1 db.Conn có sẵn. Tự commit: mỗi lệnh ghi là 1 giao dịch.
        self.db = database if isinstance(database, db.Conn) else db.connect(database, autocommit=True)
        self.lock = threading.RLock()

    def q(self, sql, *p):
        """Trả list[dict] (dict thật — FastAPI trả JSON đúng dạng object)."""
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, p).fetchall()]

    def run(self, sql, *p):
        """Ghi (chỉ dùng cho phần app khách + cảnh báo trực tiếp; tool của agent vẫn chỉ đọc)."""
        with self.lock:
            return self.db.execute(sql, p)

    @contextmanager
    def transaction(self):
        with self.lock, self.db.raw.transaction():
            yield self

    def apps(self, ids):
        return self.q("SELECT * FROM apps WHERE app_id = ANY(?)", list(ids)) if ids else []

    def alert(self, alert_id):
        """Ảnh chụp cụm tại lúc cảnh báo — đầu vào cho investigate()."""
        rows = self.q("SELECT * FROM alerts WHERE alert_id=?", alert_id)
        if not rows:
            return None
        a = rows[0]
        a["context"] = json.loads(a.get("context") or "{}")
        a["app_ids"], a["signals_on"] = json.loads(a["app_ids"]), json.loads(a["signals"])
        a["signals"] = {k: True for k in a["signals_on"]}
        a["wallets"] = [r["phone"] for r in self.apps(a["app_ids"])]
        a["cluster_id"] = a["cid"] or a["alert_id"]
        return a

    def tech_profile(self, ids):
        rows = self.apps(ids)
        n = len(rows)
        cnt = {"ip_block": sum(r["ip_type"] in ("vpn", "datacenter") for r in rows),
               "sim_new": sum(int(r["sim_age_days"]) < 30 for r in rows),
               "emulator": sum(r["is_emulator"] == "True" for r in rows),
               "hooked": sum(r["is_rooted_or_hooked"] == "True" for r in rows),
               "device_new": sum(int(r["device_first_seen_hours"]) < 24 for r in rows),
               "fast_fill": sum(int(r["fill_time_sec"]) < 90 for r in rows),
               "night": sum(int(r["applied_at"][11:13]) < 6 for r in rows)}
        bad = {k: v for k, v in cnt.items() if v >= max(2, (n + 1) // 2)}
        parts = [f"{v}/{n} {label}" for k, label in (("ip_block", "IP VPN/datacenter"), ("sim_new", "SIM < 30 ngày"),
                 ("emulator", "giả lập"), ("hooked", "máy bị hook"), ("device_new", "máy mới gắn ví < 24h"),
                 ("fast_fill", "điền đơn < 90 giây"), ("night", "nộp lúc 0–6h")) if (v := cnt[k])]
        return {"counts": cnt, "bad": bad, "summary": "; ".join(parts) or "Tín hiệu kỹ thuật bình thường."}

    def money_flow(self, ids, as_of=None):
        rows = {r["phone"]: r for r in self.apps(ids)}
        ts = self.q(f"SELECT * FROM transfers WHERE from_wallet IN ({','.join('?' * len(rows))}) AND created_at <= ? ORDER BY created_at",
                    *rows, as_of or "9999")
        out, recips, senders = defaultdict(int), set(), defaultdict(set)
        for t in ts:
            a = rows[t["from_wallet"]]
            m = (datetime.fromisoformat(t["created_at"]) - datetime.fromisoformat(a["disbursed_at"])).total_seconds() / 60
            if 0 <= m <= 120 and t["to_name"] != ai.plain(a["full_name"]).upper():
                out[a["app_id"]] += int(t["amount"])
                recips.add(t["to_id"]); senders[t["to_id"]].add(a["app_id"])
        fast = sorted(x for x, s in out.items() if s >= 0.8 * int(next(r for r in rows.values() if r["app_id"] == x)["amount"]))
        shared = {k: sorted(v) for k, v in senders.items() if len(v) >= 2}
        summary = (f"{len(fast)}/{len(rows)} hồ sơ chuyển ≥ 80% tiền vay cho người khác tên trong 2 giờ sau giải ngân"
                   + (f"; {len(shared)} tài khoản nhận tiền từ ≥ 2 hồ sơ trong cụm" if shared else ""))
        return {"fast_out_stranger": fast, "recipients": sorted(recips), "shared_recipients": shared, "summary": summary,
                "transfers": [{**t, "from_wallet": mask(t["from_wallet"]), "to_id": mask(t["to_id"])} for t in ts]}

    def timeline(self, app_id, as_of=None):
        """Dòng thời gian 1 hồ sơ (chỉ tới as_of) + số ngày quá hạn TẠI as_of, tính từ lịch trả và các lần trả."""
        rows = self.apps([app_id])
        if not rows:
            return None
        a, cut = rows[0], as_of or "9999"
        ev = [(a["applied_at"], "submit", "Nộp hồ sơ", f"{int(a['amount']):,} đ · {a['purpose']} · IP {a['ip_type']} · SIM {a['sim_age_days']} ngày".replace(",", "."))]
        for s in self.q("SELECT * FROM ekyc_sessions WHERE app_id=? ORDER BY attempt_no", app_id):
            ev.append((s["ts"], "ekyc", f"eKYC lần {s['attempt_no']}: {'đạt' if s['result'] == 'PASS' else 'trượt'}",
                       f"liveness {s['liveness_score']}" + (" · máy bị hook/root" if s["is_rooted_or_hooked"] == "True" else "")))
        if a["decided_at"]:
            ev.append((a["decided_at"], "decision", "Duyệt" if a["decision"] == "APPROVED" else "Từ chối", ""))
        if a["disbursed_at"]:
            ev.append((a["disbursed_at"], "disburse", "Giải ngân về ví chính chủ", f"{int(a['amount']):,} đ · kỳ hạn {a['term_months']} tháng".replace(",", ".")))
        for t in self.q("SELECT * FROM transfers WHERE from_wallet=?", a["phone"]):
            flags = [f for f, on in (("SIMO gắn cờ", t["simo_flag"] == "True"), ("ngoài danh bạ", t["recipient_in_contacts"] != "True"),
                                     ("lần đầu chuyển", t["prior_transfers_to_recipient"] == "0")) if on]
            ev.append((t["created_at"], "transfer", f"Chuyển {int(t['amount']):,} đ → {t['to_name']}".replace(",", "."),
                       f"{t['to_bank']} {mask(t['to_id'])}" + (f" · “{t['note']}”" if t["note"] else "") + (f" · {', '.join(flags)}" if flags else "")))
        dues = self.q("SELECT * FROM schedule WHERE app_id=? ORDER BY term_no", app_id)
        paid = {int(r["term_no"]): r for r in self.q("SELECT * FROM repayments WHERE app_id=?", app_id) if r["paid_at"] <= cut}
        for d in dues:
            ev.append((d["due_date"] + "T00:00:00", "due", f"Đến hạn kỳ {d['term_no']}", f"{int(d['total_due']):,} đ".replace(",", ".")))
        for k, r in paid.items():
            ev.append((r["paid_at"], "repay", f"Trả kỳ {k}", f"{int(r['amount']):,} đ · {r['channel']}".replace(",", ".")))
        for r in self.q("SELECT report_id, reported_at, raw_text FROM reports WHERE reporter_phone=?", a["phone"]):
            ev.append((r["reported_at"], "report", "Khách gửi tin báo lừa đảo", r["raw_text"][:120]))
        if db.has_table(self.db,"khach_loans"):
            for loan in self.q("SELECT loan_id,amount,disbursed_at FROM khach_loans WHERE phone=? AND disbursed_at<=?",a["phone"],cut):
                ev.append((loan["disbursed_at"],"disburse",f"Giải ngân khoản vay KL{loan['loan_id']}",f"{int(loan['amount']):,} đ"))
        if db.has_table(self.db,"khach_transfers"):
            for tx in self.q("SELECT tx_id,ts,amount,to_bank,to_id,status FROM khach_transfers WHERE phone=? AND ts<=?",a["phone"],cut):
                label="Đang tạm giữ, chưa chuyển" if tx["status"]=="held" else "Đã chuyển"
                ev.append((tx["ts"],"transfer",f"KT{tx['tx_id']} · {label}",f"{int(tx['amount']):,} đ · {tx['to_bank']} {mask(tx['to_id'])}"))
        # gộp theo cụm: lần cảnh báo ĐẦU (tới as_of) + số lần cập nhật sau đó — tránh ngập dòng thời gian
        als = self.q("SELECT alert_id, ts, title, cid FROM alerts WHERE app_ids LIKE ? AND ts <= ? ORDER BY ts", f'%"{app_id}"%', cut)
        seen = {}
        for al in als:
            seen.setdefault(al["cid"] or al["alert_id"], []).append(al)
        for grp in seen.values():
            more = f" · thêm {len(grp) - 1} lần cập nhật, gần nhất {grp[-1]['ts'][11:16]} {grp[-1]['ts'][8:10]}/{grp[-1]['ts'][5:7]}" if len(grp) > 1 else ""
            ev.append((grp[0]["ts"], "alert", f"Cảnh báo {grp[0]['cid'] or grp[0]['alert_id']}", grp[0]["title"] + more))
        ev = sorted(e for e in ev if e[0] <= cut)
        dpd = 0
        now = datetime.fromisoformat(cut[:19]) if as_of else None
        for d in dues:
            if int(d["term_no"]) not in paid and now and d["due_date"] + "T23:59:59" < cut:
                dpd = (now.date() - datetime.fromisoformat(d["due_date"]).date()).days
                break
        prof = {k: a[k] for k in ("app_id", "full_name", "dob", "address", "amount", "purpose", "status", "ip_type", "sim_age_days",
                                  "device_id", "is_emulator", "fill_time_sec", "wallet_age_days", "ekyc_attempts", "liveness_score")}
        prof.update(phone=mask(a["phone"]), cccd=mask(a["cccd"]), dob=a["dob"][:4],   # tối thiểu hoá: năm sinh + tỉnh
                    address=a["address"].replace(" - ", ", ").split(",")[-1].strip())
        return {"profile": prof, "as_of": as_of, "dpd": dpd,
                "events": [{"ts": e[0], "type": e[1], "title": e[2], "detail": e[3]} for e in ev]}

    def account_senders(self, account):
        return self.q("SELECT a.app_id, t.created_at, t.amount FROM transfers t JOIN apps a ON a.phone=t.from_wallet WHERE t.to_id=?", account)

    def reports_mentioning(self, recipients, wallets=(), as_of=None):
        hits, victims, self_rep = [], [], []
        wallets = set(wallets)
        for r in self.q("SELECT report_id, reporter_phone, raw_text, analysis FROM reports WHERE reported_at <= ?", as_of or "9999"):
            an = json.loads(r["analysis"])
            ind = set(an["indicators"]["accounts"] + an["indicators"]["phones"])
            if ind & set(recipients) or r["reporter_phone"] in wallets:
                hits.append({"report_id": r["report_id"], "verdict": an["verdict"], "excerpt": r["raw_text"][:140]})
                if an["reporter_is_victim"]:
                    victims.append(r["report_id"])
                    if r["reporter_phone"] in wallets:   # chính khách trong cụm tự kể bị lừa
                        self_rep.append(r["report_id"])
        s = (f"{len(hits)} tin báo nhắc tới nơi nhận tiền" + (f", {len(victims)} tin do người bị hại kể" if victims else "")
             + (f", {len(self_rep)} tin do chính khách trong cụm gửi" if self_rep else ""))
        return {"n": len(hits), "reports": hits[:5], "victim_reporters": victims, "self_reported": self_rep,
                "summary": s if hits else "Chưa có tin báo nào."}
