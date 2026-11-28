import asyncio
import json
import random
from collections import Counter, deque
from app import security
from app.backend.store import mask
from app.backend.wallet.runtime import now_iso
from .constants import MAX_EVENTS

from .scenarios import TransferScenarios


class Simulator(TransferScenarios):
    def __init__(self, wallet):
        self.wallet = wallet
        self.running, self.task, self.interval = (False, None, 2.0)
        self.stats, self.recent, self.active = (Counter(), deque(maxlen=15), deque(maxlen=40))
        self.rng = random.Random()
        self.scam_accounts = []

    def start(self, interval: float):
        self.interval = max(0.5, min(interval, 30.0))
        if not self.running:
            self.running, self.stats = (True, Counter())
            self.task = asyncio.get_running_loop().create_task(self._loop())

    def stop(self):
        self.running = False

    def status(self):
        return {
            "running": self.running,
            "interval": self.interval,
            "stats": dict(self.stats),
            "recent": list(self.recent),
            "max_events": MAX_EVENTS,
        }

    async def _loop(self):
        while self.running and self.stats["events"] < MAX_EVENTS:
            try:
                await asyncio.to_thread(self.step)
            except Exception as e:
                self.stats["errors"] += 1
                self.recent.appendleft(
                    {
                        "ts": security.vntime_now().isoformat(timespec="seconds"),
                        "text": f"Lỗi mô phỏng: {e}",
                        "decision": "error",
                    }
                )
            await asyncio.sleep(self.interval)
        self.running = False

    def step(self):
        self.stats["events"] += 1
        if not self.active or self.rng.random() < 0.4:
            self.new_loan()
        else:
            self.transfer()

    def _scam_pool(self):
        if not self.scam_accounts:
            rep = [
                a
                for r in self.wallet.tools.q("SELECT analysis FROM reports")
                for a in json.loads(r["analysis"])["indicators"]["accounts"]
            ]
            simo = [
                r["to_id"]
                for r in self.wallet.tools.q(
                    "SELECT to_id FROM simo_list ORDER BY random() LIMIT 20"
                )
            ]
            self.scam_accounts = list(dict.fromkeys(rep))[:20] + simo
        return self.scam_accounts

    def new_loan(self):
        a = self.wallet.tools.q(
            "SELECT app_id, phone, full_name, ref1_phone, ref1_name FROM apps WHERE status='DISBURSED' ORDER BY random() LIMIT 1"
        )[0]
        amount = self.rng.randrange(2000000, 20000001, 500000)
        from app.backend.events import publish

        ts = now_iso()
        with self.wallet.tools.transaction():
            lid = self.wallet.tools.q(
                "INSERT INTO khach_loans (phone,app_id,amount,disbursed_at) VALUES (?,?,?,?) RETURNING loan_id",
                a["phone"],
                a["app_id"],
                amount,
                ts,
            )[0]["loan_id"]
            publish(self.wallet.tools, "loan", "KL" + str(lid), a["app_id"], ts, simulated=True)
        self.active.append((a, amount))
        self.stats["loans"] += 1
        self.stats["loan_amount"] += amount
        self.recent.appendleft(
            {
                "ts": now_iso(),
                "decision": "loan",
                "text": f"{a['full_name']} vay {amount:,} đ — giải ngân về ví {mask(a['phone'])}".replace(
                    ",", "."
                ),
            }
        )
