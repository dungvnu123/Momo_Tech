import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]


def register(app, tools, adapter, META):
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
                "time_to_alert": ttd, "rules_baseline": {"n": 61401, "fraud": 54, "victims_as_fraud": 23}, "ai_mode": "gemini"}
