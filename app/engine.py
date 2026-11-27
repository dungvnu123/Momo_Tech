# path: app/engine.py
"""Bộ máy realtime: nhận từng sự kiện theo thời gian (nộp hồ sơ, chuyển tiền, tin báo), cập nhật DẦN đồ thị
(union-find chỉ nối thêm, dữ liệu không bị xoá) và sinh CẢNH BÁO khi một cụm vượt ngưỡng hoặc có bằng chứng mới.

Mọi quyết định chỉ dùng dữ liệu ĐÃ XẢY RA tới thời điểm sự kiện (không nhìn trước tương lai).
ponytail: trạng thái giữ trong RAM của 1 tiến trình; chạy thật thì lưu trạng thái (snapshot) để khởi động lại không mất.
"""
from collections import defaultdict
from datetime import datetime

from . import ai

SEV_W = {"khan": 3, "cao": 2, "tb": 1}


class Engine:
    def __init__(self):
        self.uf, self.members, self.reports = {}, defaultdict(set), defaultdict(set)
        self.apps, self.by_wallet = {}, {}
        self.sig = defaultdict(set)
        self.key_count, self.key_first = defaultdict(int), {}
        self.out2h = defaultdict(int)
        self.reported = defaultdict(int)          # tài khoản/ví/hotline → số tin báo đã nhận TỚI LÚC NÀY
        self.cid, self.next_cid, self.last_sig = {}, 1, {}
        self.alerts = []
        self.paid = defaultdict(set)              # app → các kỳ ĐÃ trả tới lúc này

    # ── union-find trên node: "A:app", khoá dùng chung "dev:…", "rcv:…", tin báo "R:…" ──
    def find(self, x):
        self.uf.setdefault(x, x)
        while self.uf[x] != x:
            self.uf[x] = self.uf[self.uf[x]]
            x = self.uf[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if len(self.members[ra]) + len(self.reports[ra]) < len(self.members[rb]) + len(self.reports[rb]):
            ra, rb = rb, ra
        self.uf[rb] = ra
        self.members[ra] |= self.members.pop(rb, set())
        self.reports[ra] |= self.reports.pop(rb, set())
        ca, cb = self.cid.pop(ra, None), self.cid.pop(rb, None)
        keep = min((c for c in (ca, cb) if c), default=None)   # giữ mã cụm cũ hơn → lịch sử cảnh báo liền mạch
        if keep:
            self.cid[ra] = keep
        return ra

    def _key(self, app_id, key, kind_sig):
        self.key_count[key] += 1
        if self.key_count[key] == 1:
            self.key_first[key] = app_id
        else:   # chỉ những hồ sơ THẬT SỰ dùng chung khoá này mới mang tín hiệu
            self.sig[app_id].add(kind_sig)
            self.sig[self.key_first[key]].add(kind_sig)
        return self.union("A:" + app_id, key)

    # ── sự kiện ──────────────────────────────────────────────────────────────────────
    def apply(self, a, ts):
        x = a["app_id"]
        self.apps[x] = a
        self.by_wallet[a["phone"]] = x
        self.members[self.find("A:" + x)].add(x)
        if a["ip_type"] in ("vpn", "datacenter"):
            self.sig[x].add("ip_vpn_dc")
        if int(a["sim_age_days"]) < 30:
            self.sig[x].add("sim_new")
        if a["is_emulator"] == "True":
            self.sig[x].add("emulator")
        if (int(a["device_first_seen_hours"]) < 24 or a["is_rooted_or_hooked"] == "True"
                or float(a["liveness_score"]) < 0.85 or int(a["ekyc_attempts"]) >= 3):
            self.sig[x].add("ekyc")
        root = self._key(x, "dev:" + a["device_id"], "device_shared")
        root = self._key(x, "ref:" + a["ref1_phone"], "ref_shared")
        root = self._key(x, "ref:" + a["ref2_phone"], "ref_shared")
        if a["ip_type"] in ("vpn", "datacenter"):
            root = self._key(x, "ip:" + a["ip"].rsplit(".", 1)[0], "ip_block")
        if int(a["sim_age_days"]) < 30:
            root = self._key(x, "sim:" + a["phone"][:8], "sim_block")
        return self.evaluate(root, ts, "apply")

    def transfer(self, t, ts):
        x = self.by_wallet.get(t["from_wallet"])
        if not x:
            return None
        a = self.apps[x]
        m = (datetime.fromisoformat(t["created_at"]) - datetime.fromisoformat(a["disbursed_at"])).total_seconds() / 60
        amt, stranger = int(t["amount"]), t["to_name"] != ai.plain(a["full_name"]).upper()
        # 1) Cảnh báo lúc chuyển tiền — chỉ biết tin báo ĐÃ có tới giờ
        ctx = {"amount": amt, "loan_amount": int(a["amount"]), "minutes_after_disbursal": round(m), "to_name_matches_borrower": not stranger,
               "recipient_in_contacts": t["recipient_in_contacts"] == "True",
               "contact_saved_minutes_ago": int(t["contact_saved_minutes_ago"]) if t["contact_saved_minutes_ago"] else None,
               "prior_transfers_to_recipient": int(t["prior_transfers_to_recipient"]), "simo_flag": t["simo_flag"] == "True",
               "to_wallet_age_days": t["to_wallet_age_days"], "note": t["note"], "times_reported": self.reported.get(t["to_id"], 0)}
        chk = ai.check_transfer(ctx)
        if chk["decision"] == "hold":
            self._emit({"kind": "transfer", "ts": ts, "cid": None, "app_ids": [x], "transfer_id": t["transfer_id"],
                        "title": f"Tạm giữ giao dịch {amt:,} đ của {x} — {chk['reasons'][0] if chk['reasons'] else ''}".replace(",", "."),
                        "severity": "khan", "confidence": 0.8 if ctx["simo_flag"] or ctx["times_reported"] else 0.6,
                        "signals": ["simo"] if ctx["simo_flag"] else ["fast_out_stranger"], "size": 1, "n_pending": 0, "n_reports": ctx["times_reported"],
                        "suspected_type": "transfer_hold", "reason": "; ".join(chk["reasons"])})
        # 2) Cập nhật đồ thị
        if t["simo_flag"] == "True":
            self.sig[x].add("simo")
        if m <= 120 and stranger:
            self.out2h[x] += amt
            if self.out2h[x] >= 0.8 * int(a["amount"]):
                self.sig[x].add("fast_out_stranger")
        root = self.find("A:" + x)
        if (m <= 120 and stranger and t["to_id"] not in self.by_wallet and t["to_is_merchant"] != "True"
                and amt >= 0.3 * int(a["amount"]) and t["prior_transfers_to_recipient"] == "0"):
            root = self._key(x, "rcv:" + t["to_id"], "shared_recipient")
            if t["to_wallet_opened_device"]:
                root = self._key(x, "odev:" + t["to_wallet_opened_device"], "recipient_wallet_farm")
        return self.evaluate(root, ts, "transfer")

    def repayment(self, r, ts):
        self.paid[r["app_id"]].add(int(r["term_no"]))
        return None

    def due_check(self, app_id, ts):
        """Hậu kiểm: đến hạn kỳ 1 + 10 ngày mà chưa trả → tín hiệu 'fpd'. Đứng riêng chỉ là rủi ro tín dụng (không cảnh báo);
        nằm trong cụm có quan hệ thì làm cụm nặng thêm."""
        if 1 in self.paid[app_id] or app_id not in self.apps:
            return None
        self.sig[app_id].add("fpd")
        return self.evaluate(self.find("A:" + app_id), ts, "fpd")

    def report(self, r, analysis, ts):
        if analysis["verdict"] == "safe":
            return None
        node = "R:" + r["report_id"]
        root = self.find(node)
        self.reports[root].add(r["report_id"])
        for acc in analysis["indicators"]["accounts"] + analysis["indicators"]["phones"]:
            self.reported[acc] += 1
            root = self.union(node, "rcv:" + acc)
            root = self.union(node, "hot:" + acc)
        if r["reporter_phone"] in self.by_wallet:
            root = self.union(node, "A:" + self.by_wallet[r["reporter_phone"]])
        return self.evaluate(root, ts, "report")

    # ── đánh giá cụm vừa đổi → có thể sinh cảnh báo ─────────────────────────────────────
    def evaluate(self, root, ts, cause):
        ids = self.members.get(root, set())
        reps = self.reports.get(root, set())
        if len(ids) < 2 and not (reps and ids):
            return None
        cnt = defaultdict(int)
        for x in ids:
            for k in self.sig[x]:
                cnt[k] += 1
        n = len(ids)
        signals = {"ref_hub": cnt["ref_shared"] >= 5, "device_hub": cnt["device_shared"] >= 5,
                   "ip_block": cnt["ip_block"] >= 2, "sim_block": cnt["sim_block"] >= 2, "emulator": cnt["emulator"] >= 2,
                   "ekyc": cnt["ekyc"] >= max(2, n // 2), "fast_out_stranger": cnt["fast_out_stranger"] >= 1,
                   "shared_recipient": cnt["shared_recipient"] >= 2, "simo": cnt["simo"] >= 1, "fpd_cluster": cnt["fpd"] >= 2}
        # chờ giải ngân TẠI thời điểm ts: chưa có quyết định, hoặc đã duyệt nhưng chưa giải ngân
        n_pending = sum(1 for x in ids if (not self.apps[x]["decided_at"] or self.apps[x]["decided_at"] > ts)
                        or (self.apps[x]["decision"] == "APPROVED" and self.apps[x]["disbursed_at"] > ts))
        summary = {"cluster_id": None, "size": n, "signals": signals, "n_reports": len(reps), "n_pending": n_pending}
        tri = ai.triage_clusters([summary])[0]
        if tri["decision"] != "investigate":
            return None
        on = tuple(sorted(k for k, v in signals.items() if v))
        state = (on, len(reps), n, n_pending)
        if root not in self.cid:
            self.cid[root] = f"C{self.next_cid:05d}"
            self.next_cid += 1
        cid = self.cid[root]
        prev = self.last_sig.get(cid)
        if prev == state:
            return None
        self.last_sig[cid] = state
        new = [k for k in on if not prev or k not in prev[0]]
        sev = ("khan" if n_pending and (reps or signals["shared_recipient"] or signals["simo"] or signals["ref_hub"] or signals["device_hub"] or signals["fpd_cluster"])
               else "cao" if reps or len(on) >= 3 or signals["shared_recipient"] else "tb")
        self._emit({"kind": "cluster", "ts": ts, "cid": cid, "app_ids": sorted(ids), "transfer_id": None,
                    "title": _title(cause, new, n, len(reps), prev, signals), "severity": sev, "confidence": tri["confidence"],
                    "signals": list(on), "size": n, "n_pending": n_pending, "n_reports": len(reps),
                    "suspected_type": tri["suspected_type"], "reason": tri["reason"]})
        return cid

    def _emit(self, al):
        al["alert_id"] = f"AL{len(self.alerts) + 1:06d}"
        al["day"] = al["ts"][:10]
        al["priority"] = round(SEV_W[al["severity"]] * 10 + al["confidence"] * 10 + min(al["size"], 10) + 2 * al["n_pending"], 2)
        self.alerts.append(al)


SIG_VI = {"ref_hub": "chung SĐT tham chiếu", "device_hub": "dùng chung thiết bị", "ip_block": "cùng dải IP VPN/datacenter",
          "sim_block": "SIM cùng lô mới kích hoạt", "emulator": "máy giả lập", "ekyc": "phiên eKYC bất thường",
          "fast_out_stranger": "rút gần hết tiền vay cho người lạ", "shared_recipient": "đổ tiền về cùng tài khoản", "simo": "người nhận bị SIMO gắn cờ", "fpd_cluster": "cùng quá hạn ngay kỳ đầu"}


def _title(cause, new, n, n_reports, prev, signals):
    if cause == "fpd" and "fpd_cluster" in new:
        return f"{n} hồ sơ liên quan cùng quá hạn ngay kỳ đầu"
    if cause == "report" and n_reports:
        return f"Tin báo mới nối vào {n} khoản vay — tổng {n_reports} tin báo"
    if "shared_recipient" in new:
        return f"{n} ví vừa vay đã đổ tiền về cùng tài khoản"
    if new:
        return f"{n} hồ sơ: {', '.join(SIG_VI[k] for k in new)}"
    if prev and n > prev[2]:
        return f"Cụm lớn thêm: {n} hồ sơ ({', '.join(SIG_VI[k] for k, v in signals.items() if v)})"
    return f"{n} hồ sơ có thay đổi"


def events(apps, transfers, reports, repayments=(), schedule=(), data_end="9999"):
    """Gộp mọi sự kiện, sắp theo thời gian. (thời điểm, thứ tự, loại, dữ liệu).
    due_check = lịch hẹn giờ của chính hệ thống (đến hạn kỳ 1 + 10 ngày) — không phải dữ liệu tương lai."""
    from datetime import date, timedelta
    ev = [(a["applied_at"], 0, "apply", a) for a in apps]
    ev += [(t["created_at"], 1, "transfer", t) for t in transfers]
    ev += [(r["reported_at"], 2, "report", r) for r in reports]
    ev += [(r["paid_at"], 3, "repayment", r) for r in repayments]
    for s in schedule:
        if s["term_no"] == "1":
            ck = (date.fromisoformat(s["due_date"]) + timedelta(days=10)).isoformat() + "T00:00:00"
            if ck <= data_end:
                ev.append((ck, 4, "due_check", s["app_id"]))
    ev.sort(key=lambda e: (e[0], e[1]))
    return ev
