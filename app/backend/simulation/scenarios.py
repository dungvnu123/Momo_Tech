from app.backend import mock_ai as ai
from app.backend.wallet.runtime import now_iso
from .constants import KINDS, BANKS

from app.backend.wallet.schemas import TransferIn
from app.backend.wallet.transfers import execute_transfer


class TransferScenarios:
    def transfer(self):
        a, loan = self.active.popleft()
        kind = self.rng.choices([k[0] for k in KINDS], [k[2] for k in KINDS])[0]
        me = ai.plain(a["full_name"]).upper()
        acct = "".join((self.rng.choice("0123456789") for _ in range(12)))
        if kind == "self":
            body = dict(
                to_type="bank",
                to_id=acct,
                to_bank=self.rng.choice(BANKS),
                to_name=me,
                amount=int(loan * self.rng.uniform(0.8, 1)),
                note="",
            )
        elif kind == "family":
            self.wallet.tools.run(
                "INSERT INTO khach_contacts VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                a["phone"],
                a["ref1_phone"],
                a["ref1_name"],
                "2025-01-01T00:00:00",
            )
            body = dict(
                to_type="momo_wallet",
                to_id=a["ref1_phone"],
                to_bank="MoMo",
                to_name=ai.plain(a["ref1_name"]).upper(),
                amount=int(loan * self.rng.uniform(0.1, 0.5)),
                note=self.rng.choice(["gui me", "tien nha", ""]),
            )
        elif kind == "shop":
            body = dict(
                to_type="bank",
                to_id=acct,
                to_bank=self.rng.choice(BANKS),
                to_name="CUA HANG " + self.rng.choice(["MINH ANH", "HOANG LONG", "THU TRANG"]),
                amount=int(loan * self.rng.uniform(0.1, 0.4)),
                note=self.rng.choice(["tien phong thang 11", "mua dien thoai", "hoc phi"]),
            )
        elif kind == "coached":
            pool = self._scam_pool() + [acct] * 5
            body = dict(
                to_type="bank",
                to_id=self.rng.choice(pool),
                to_bank=self.rng.choice(BANKS),
                to_name="NGUYEN VAN " + self.rng.choice(["TUNG", "HAU", "QUAN"]),
                amount=loan,
                note=self.rng.choice(["xac minh ho so", "phi giai ngan", "chuyen tien", ""]),
            )
        elif kind == "collect":
            body = dict(
                to_type="bank",
                to_id=acct,
                to_bank="VCB",
                to_name="CONG TY THU HOI NO AN BINH",
                amount=self.rng.randrange(500000, 3000001, 100000),
                note="tra no FinVay",
            )
        else:
            body = dict(
                to_type="bank",
                to_id=acct,
                to_bank="VIB",
                to_name="NGUYEN VAN BINH",
                amount=int(loan * self.rng.uniform(0.5, 0.9)),
                note="chuyen gap cho me",
            )
        acc = {
            "phone": a["phone"],
            "app_id": a["app_id"],
            "display_name": a["full_name"],
            "balance": loan if kind == "relative" else None,
        }
        tx = TransferIn(
            **body, save_contact=kind == "coached" and self.rng.random() < 0.3, confirm=False
        )
        r = execute_transfer(self.wallet, acc, tx, source="sim")
        if r.get("needs_confirm"):
            if self.rng.random() < 0.5:
                r = {**r, "decision": "cancelled"}
            else:
                r = execute_transfer(
                    self.wallet, acc, tx.model_copy(update={"confirm": True}), source="sim"
                )
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
        label = dict(((k[0], k[1]) for k in KINDS))[kind]
        self.recent.appendleft(
            {
                "ts": now_iso(),
                "decision": dec,
                "kind": label,
                "text": f"{a['full_name']} chuyển {body['amount']:,} đ → {body['to_name']}".replace(
                    ",", "."
                ),
            }
        )
