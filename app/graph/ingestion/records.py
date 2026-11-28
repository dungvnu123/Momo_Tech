"""Project only the event's source records; no full graph rebuild."""

import json
from datetime import datetime

from app.graph import normalize
from app.graph.builder import _Writer


def application(store, row):
    writer = _Writer(store)
    identifier = row["app_id"]
    store.connection.execute(
        "INSERT OR REPLACE INTO applications VALUES (?,?,?)",
        (identifier, normalize.phone(row["phone"]), json.dumps(row)),
    )
    store.connection.execute(
        "DELETE FROM edges WHERE source_table='applications' AND source_id=?", (identifier,)
    )
    root = writer.node("app:" + identifier, "Application", app_id=identifier)
    links = [(normalize.account("momo_wallet", "", row["phone"]), "Account", "HAS_WALLET", "")]
    if row.get("device_id"):
        links.append(("device:" + row["device_id"], "Device", "USES_DEVICE", ""))
    if row.get("cccd"):
        links.append(("person:" + row["cccd"], "Person", "APPLIED_BY", ""))
    for key in ("ref1", "ref2"):
        if row.get(key + "_phone"):
            links.append(
                ("phone:" + normalize.phone(row[key + "_phone"]), "Phone", "REFERENCE", key)
            )
    if row.get("ip") and row.get("ip_type") in {"vpn", "datacenter"}:
        links.append(("ipblock:" + normalize.ip_block(row["ip"]), "IpBlock", "FROM_IP", ""))
    if row.get("sim_age_days") not in (None, "") and int(row["sim_age_days"]) < 30:
        links.append(("simblock:" + normalize.phone(row["phone"])[:8], "SimBlock", "SIM_IN", ""))
    for target, kind, edge, suffix in links:
        writer.node(target, kind)
        writer.edge(
            root, target, edge, "applications", identifier, row["applied_at"], suffix=suffix
        )


def loan(store, row, app_id):
    writer = _Writer(store)
    identifier = "KL" + str(row["loan_id"])
    store.connection.execute(
        "INSERT OR REPLACE INTO live_loans VALUES (?,?)",
        (identifier, json.dumps({**row, "app_id": app_id})),
    )
    store.connection.execute(
        "DELETE FROM edges WHERE source_table='live_loans' AND source_id=?", (identifier,)
    )
    node = writer.node("loan:" + identifier, "Loan")
    writer.edge(
        "app:" + app_id,
        node,
        "HAS_LOAN",
        "live_loans",
        identifier,
        row["disbursed_at"],
        amount=int(row["amount"]),
    )


def transfer(store, row, app, event_sequence=None):
    writer = _Writer(store)
    identifier = "KT" + str(row["tx_id"])
    context = json.loads(row.get("context") or "{}")
    original = {
        **row,
        "transfer_id": identifier,
        "from_wallet": row["phone"],
        "created_at": row["ts"],
        "backend_source": {"table": "khach_transfers", "id": identifier},
    }
    store.connection.execute(
        "INSERT OR REPLACE INTO wallet_transfers VALUES (?,?,?)",
        (identifier, normalize.phone(row["phone"]), json.dumps(original)),
    )
    store.connection.execute(
        "DELETE FROM edges WHERE source_table='wallet_transfers' AND source_id=?", (identifier,)
    )
    target = normalize.account(row["to_type"], row["to_bank"], row["to_id"])
    writer.node(target, "Account")
    elapsed = context.get("minutes_after_disbursal")
    if elapsed is None and app.get("disbursed_at"):
        elapsed = (
            datetime.fromisoformat(row["ts"]) - datetime.fromisoformat(app["disbursed_at"])
        ).total_seconds() / 60
    writer.edge(
        "app:" + app["app_id"],
        target,
        "SENT_TO" if row["status"] == "done" else "TRANSFER_ATTEMPT",
        "wallet_transfers",
        identifier,
        row["ts"],
        amount=int(row["amount"]),
        status=row["status"],
        event_sequence=event_sequence,
        loan_id=row.get("loan_id"),
        loan_amount=context.get("loan_amount"),
        recipient_resolved=True,
        minutes_after_disbursal=elapsed,
        pct_of_loan=int(row["amount"])
        / max(context.get("loan_amount") or int(app["amount"]), 1)
        * 100,
        to_name=row["to_name"],
        simo_flag=context.get("simo_flag"),
        recipient_in_contacts=context.get("recipient_in_contacts"),
        prior_transfers_to_recipient=context.get("prior_transfers_to_recipient"),
    )


def report(store, row, analysis):
    writer = _Writer(store)
    store.connection.execute(
        "INSERT OR REPLACE INTO scam_reports VALUES (?,?)", (row["report_id"], json.dumps(row))
    )
    store.connection.execute(
        "DELETE FROM edges WHERE source_table='scam_reports' AND source_id=?", (row["report_id"],)
    )
    node = writer.node("report:" + row["report_id"], "Report")
    wallet = writer.node(normalize.account("momo_wallet", "", row["reporter_phone"]), "Account")
    writer.edge(node, wallet, "REPORTED_BY", "scam_reports", row["report_id"], row["reported_at"])
    if analysis is not None:
        store.persist_report(row["report_id"], row["raw_text"], analysis, transaction=False)
