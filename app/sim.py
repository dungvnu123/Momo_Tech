# path: app/sim.py
"""Bộ mô phỏng hoạt động trực tiếp: tự sinh khoản vay + giao dịch chuyển tiền ngẫu nhiên để hệ thống "đang sống" khi demo.

Mọi giao dịch đi qua ĐÚNG luồng của app khách (khach.execute_transfer → ai.check_transfer): tạm giữ thì sinh cảnh báo.
Nhãn "kịch bản" (bình thường / bị dụ vay / giả thu nợ / người thân nhờ gấp) chỉ để hiển thị & đo — bộ kiểm tra KHÔNG thấy nhãn này.
ponytail: chạy trong 1 tiến trình (asyncio task); nhiều tiến trình thì tách thành worker riêng.
"""
import asyncio
import json
import random
from collections import Counter, deque

from . import khach, security
from .backend import mock_ai as ai
from .backend.store import mask

KINDS = [  # (mã, nhãn, trọng số)
    ("self", "Rút về tài khoản chính chủ", 30),
    ("family", "Chuyển cho người thân", 22),
    ("shop", "Trả tiền phòng / mua hàng", 20),
    ("coached", "Bị dụ vay rồi chuyển hết", 13),
    ("collect", "Giả bên thu hồi nợ", 8),
    ("relative", "Người thân nhờ chuyển gấp", 7),
]
BANKS = ["VCB", "TCB", "MBB", "ACB", "VPB", "BIDV", "CTG", "TPB", "STB", "VIB"]
MAX_EVENTS = 2000


class Simulator:
    def __init__(self):
        self.running, self.task, self.interval = False, None, 2.0
        self.stats, self.recent, self.active = Counter(), deque(maxlen=15), deque(maxlen=40)
        self.rng = random.Random()
        self.scam_accounts = []

    # ── điều khiển ──────────────────────────────────────────────────────────────────
    def start(self, interval: float):
        self.interval = max(0.5, min(interval, 30.0))
        if not self.running:
            self.running, self.stats = True, Counter()
            self.task = asyncio.get_running_loop().create_task(self._loop())

    def stop(self):
        self.running = False

    def status(self):
        return {"running": self.running, "interval": self.interval, "stats": dict(self.stats), "recent": list(self.recent),
                "max_events": MAX_EVENTS}

    async def _loop(self):
        while self.running and self.stats["events"] < MAX_EVENTS:
            try:
                await asyncio.to_thread(self.step)   # truy vấn DB chạy ở luồng riêng, không chặn web
            except Exception as e:   # 1 sự kiện lỗi không được làm chết cả bộ mô phỏng
                self.stats["errors"] += 1
                self.recent.appendleft({"ts": security.vntime_now().isoformat(timespec="seconds"), "text": f"Lỗi mô phỏng: {e}", "decision": "error"})
            await asyncio.sleep(self.interval)
        self.running = False

    # ── 1 bước ──────────────────────────────────────────────────────────────────────
    def step(self):
        self.stats["events"] += 1
        if not self.active or self.rng.random() < 0.4:
            self.new_loan()
        else:
            self.transfer()

    def _scam_pool(self):
        if not self.scam_accounts:   # tài khoản lừa: bị báo nhiều + SIMO gắn cờ (+ tài khoản mới tinh sinh lúc chạy)
            rep = [a for r in khach.tools.q("SELECT analysis FROM reports") for a in json.loads(r["analysis"])["indicators"]["accounts"]]
            simo = [r["to_id"] for r in khach.tools.q("SELECT to_id FROM simo_list ORDER BY random() LIMIT 20")]
            self.scam_accounts = list(dict.fromkeys(rep))[:20] + simo
        return self.scam_accounts

    def new_loan(self):
        a = khach.tools.q("SELECT app_id, phone, full_name, ref1_phone, ref1_name FROM apps WHERE status='DISBURSED' ORDER BY random() LIMIT 1")[0]
        amount = self.rng.randrange(2_000_000, 20_000_001, 500_000)
        khach.tools.run("INSERT INTO khach_loans (phone, amount, disbursed_at) VALUES (?,?,?)", a["phone"], amount, khach.now_iso())
        self.active.append((a, amount))
        self.stats["loans"] += 1
        self.stats["loan_amount"] += amount
        self.recent.appendleft({"ts": khach.now_iso(), "decision": "loan",
                                "text": f"{a['full_name']} vay {amount:,} đ — giải ngân về ví {mask(a['phone'])}".replace(",", ".")})

    def transfer(self):
        a, loan = self.active.popleft()
        kind = self.rng.choices([k[0] for k in KINDS], [k[2] for k in KINDS])[0]
        me = ai.plain(a["full_name"]).upper()
        acct = "".join(self.rng.choice("0123456789") for _ in range(12))
        if kind == "self":
            body = dict(to_type="bank", to_id=acct, to_bank=self.rng.choice(BANKS), to_name=me, amount=int(loan * self.rng.uniform(.8, 1)), note="")
        elif kind == "family":   # người thân đã lưu trong danh bạ từ lâu
            khach.tools.run("INSERT INTO khach_contacts VALUES (?,?,?,?) ON CONFLICT DO NOTHING", a["phone"], a["ref1_phone"], a["ref1_name"], "2025-01-01T00:00:00")
            body = dict(to_type="momo_wallet", to_id=a["ref1_phone"], to_bank="MoMo", to_name=ai.plain(a["ref1_name"]).upper(),
                        amount=int(loan * self.rng.uniform(.1, .5)), note=self.rng.choice(["gui me", "tien nha", ""]))
        elif kind == "shop":
            body = dict(to_type="bank", to_id=acct, to_bank=self.rng.choice(BANKS), to_name="CUA HANG " + self.rng.choice(["MINH ANH", "HOANG LONG", "THU TRANG"]),
                        amount=int(loan * self.rng.uniform(.1, .4)), note=self.rng.choice(["tien phong thang 11", "mua dien thoai", "hoc phi"]))
        elif kind == "coached":
            pool = self._scam_pool() + [acct] * 5
            body = dict(to_type="bank", to_id=self.rng.choice(pool), to_bank=self.rng.choice(BANKS), to_name="NGUYEN VAN " + self.rng.choice(["TUNG", "HAU", "QUAN"]),
                        amount=loan, note=self.rng.choice(["xac minh ho so", "phi giai ngan", "chuyen tien", ""]))
        elif kind == "collect":
            body = dict(to_type="bank", to_id=acct, to_bank="VCB", to_name="CONG TY THU HOI NO AN BINH",
                        amount=self.rng.randrange(500_000, 3_000_001, 100_000), note="tra no FinVay")
        else:   # relative
            body = dict(to_type="bank", to_id=acct, to_bank="VIB", to_name="NGUYEN VAN BINH", amount=int(loan * self.rng.uniform(.5, .9)), note="chuyen gap cho me")
        acc = {"phone": a["phone"], "app_id": a["app_id"], "display_name": a["full_name"],
               "balance": loan if kind == "relative" else None}   # kịch bản người thân: theo dõi số dư = khoản vay
        tx = khach.TransferIn(**body, save_contact=(kind == "coached" and self.rng.random() < 0.3), confirm=False)
        r = khach.execute_transfer(acc, tx, source="sim")
        if r.get("needs_confirm"):   # khách đọc cảnh báo: một nửa huỷ, một nửa vẫn chuyển
            if self.rng.random() < 0.5:
                r = {**r, "decision": "cancelled"}
            else:
                r = khach.execute_transfer(acc, tx.model_copy(update={"confirm": True}), source="sim")
        dec = r["decision"]
        self.stats["transfers"] += 1
        self.stats[f"dec_{dec}"] += 1
        self.stats[f"kind_{kind}"] += 1
        if kind in ("coached", "collect") and dec == "hold":
            self.stats["scam_blocked"] += 1
        if kind in ("coached", "collect"):
            self.stats["scam_total"] += 1
        if kind in ("self", "family", "shop") and dec != "allow":
            self.stats["benign_flagged"] += 1
        label = dict((k[0], k[1]) for k in KINDS)[kind]
        self.recent.appendleft({"ts": khach.now_iso(), "decision": dec, "kind": label,
                                "text": f"{a['full_name']} chuyển {body['amount']:,} đ → {body['to_name']}".replace(",", ".")})


SIM = Simulator()
