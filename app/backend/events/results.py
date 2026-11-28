"""Case persistence and bank-scoped, unverified recipient links."""

import json

from app import db
from app.graph.normalize import account


def persist_case(store, alert, case):
    with store.transaction():
        store.run(
            "INSERT OR REPLACE INTO cases VALUES (?,?,?,?,?,?)",
            alert["alert_id"],
            alert["cid"],
            case["verdict"],
            json.dumps(case["members"]),
            json.dumps(case["victims"]),
            json.dumps(case, ensure_ascii=False),
        )
        store.run(
            "UPDATE alerts SET verdict=?,case_conf=? WHERE alert_id=?",
            case["verdict"],
            case["confidence"],
            alert["alert_id"],
        )
        if not db.has_table(store.db, "ai_case_recipients"):
            return
        from app.backend.agent_tools import BackendAgentTools
        from app.backend.evidence.transactions import transaction_rows

        store.run("DELETE FROM ai_case_recipients WHERE alert_id=?", alert["alert_id"])
        links = {}
        for row in transaction_rows(BackendAgentTools(store, alert)):
            try:
                key = account(row["to_type"], row["to_bank"], row["to_id"])
            except ValueError:
                continue
            links.setdefault(key, set()).add(row["application_id"])
        for key, ids in links.items():
            store.run(
                "INSERT INTO ai_case_recipients (alert_id,recipient_key,app_ids,assessment,mode) VALUES (?,?,?,?,?)",
                alert["alert_id"],
                key,
                json.dumps(sorted(ids)),
                json.dumps(case.get("cluster_assessment")),
                case.get("mode", "unknown"),
            )
