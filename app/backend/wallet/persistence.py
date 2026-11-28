"""Transactional wallet writes and their outbox notifications."""

import json
from uuid import uuid4

from fastapi import HTTPException

from app.backend.events import publish


def loan(store, acc, amount, ts):
    with store.transaction():
        row = store.q(
            "INSERT INTO khach_loans (phone,app_id,amount,disbursed_at) VALUES (?,?,?,?) RETURNING loan_id",
            acc["phone"],
            acc["app_id"],
            amount,
            ts,
        )[0]
        store.run("UPDATE khach_accounts SET balance=balance+? WHERE phone=?", amount, acc["phone"])
        publish(store, "loan", "KL" + str(row["loan_id"]), acc["app_id"], ts)
    return row["loan_id"]


def report(store, acc, msg_id, text, result, ts, notify):
    with store.transaction():
        message = store.q(
            "SELECT report_id FROM khach_inbox WHERE msg_id=? AND phone=? FOR UPDATE",
            msg_id,
            acc["phone"],
        )[0]
        if message["report_id"]:
            return json.loads(
                store.q("SELECT analysis FROM reports WHERE report_id=?", message["report_id"])[0][
                    "analysis"
                ]
            )
        rid = "TBL" + uuid4().hex
        store.run(
            "INSERT INTO reports VALUES (?,?,?,?,?,?)",
            rid,
            ts,
            acc["phone"],
            "App FinVay",
            text,
            json.dumps(result, ensure_ascii=False),
        )
        store.run(
            "UPDATE khach_inbox SET reported_verdict=?,is_read=TRUE,report_id=? WHERE msg_id=?",
            result["verdict"],
            rid,
            msg_id,
        )
        alert_id = notify() if result["verdict"] != "safe" else None
        publish(store, "report", rid, acc["app_id"], ts, alert_id=alert_id)
    return result


def transfer(store, acc, body, ctx, decision, source, ts, notify):
    status = "held" if decision["decision"] == "hold" else "done"
    with store.transaction():
        if source == "app" and status == "done":
            updated = store.q(
                "UPDATE khach_accounts SET balance=balance-? WHERE phone=? AND balance>=? RETURNING phone",
                body.amount,
                acc["phone"],
                body.amount,
            )
            if not updated:
                raise HTTPException(400, "Số dư không đủ tại thời điểm thực hiện giao dịch")
        tx_id = store.q(
            "INSERT INTO khach_transfers (phone,ts,to_type,to_id,to_bank,to_name,amount,note,decision,reasons,status,app_id,loan_id,context) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING tx_id",
            acc["phone"],
            ts,
            body.to_type,
            ctx["to_id"],
            body.to_bank.strip().upper(),
            body.to_name,
            body.amount,
            body.note,
            decision["decision"],
            json.dumps(decision["reasons"], ensure_ascii=False),
            status,
            acc["app_id"],
            ctx.get("loan_id"),
            json.dumps(ctx, ensure_ascii=False),
        )[0]["tx_id"]
        transfer_id = "KT" + str(tx_id)
        alert_id = notify(transfer_id) if status == "held" else None
        publish(
            store,
            "transfer",
            transfer_id,
            acc["app_id"],
            ts,
            alert_id=alert_id,
            simulated=source == "sim",
        )
    return {**decision, "status": status, "transfer_id": transfer_id, "context": ctx}
