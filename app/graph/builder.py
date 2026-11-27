import csv
import json
from datetime import datetime
from pathlib import Path

from . import normalize
from .store import GraphStore, TABLES

REQUIRED = {
    "applications": {"app_id", "phone", "device_id", "applied_at", "disbursed_at", "amount"},
    "wallet_transfers": {
        "transfer_id", "from_wallet", "created_at", "to_type", "to_id", "to_bank", "amount",
    },
    "scam_reports": {"report_id", "reported_at", "reporter_phone", "raw_text"},
}
IDS = {"applications": "app_id", "wallet_transfers": "transfer_id", "scam_reports": "report_id"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _import_csv(store: GraphStore, directory: Path) -> None:
    for table in TABLES:
        with (directory / f"{table}.csv").open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not REQUIRED[table] <= set(reader.fieldnames or ()):
                raise ValueError(f"Missing required columns in {table}.csv")
            for row in reader:
                identifier = row[IDS[table]]
                if not identifier:
                    raise ValueError(f"Empty record ID in {table}.csv")
                if table == "scam_reports":
                    store.connection.execute("INSERT INTO scam_reports VALUES (?, ?)", (identifier, _json(row)))
                else:
                    wallet = normalize.phone(row["phone" if table == "applications" else "from_wallet"])
                    store.connection.execute(
                        f"INSERT INTO {table} VALUES (?, ?, ?)", (identifier, wallet, _json(row))
                    )


class _Writer:
    def __init__(self, store: GraphStore):
        self.connection = store.connection

    def node(self, identifier, kind, **attributes):
        self.connection.execute(
            "INSERT OR IGNORE INTO nodes VALUES (?, ?, ?)", (identifier, kind, _json(attributes))
        )
        return identifier

    def edge(self, source, target, kind, table, record, observed_at, *, suffix="", **attributes):
        identifier = f"{table}:{record}:{kind}" + (f":{suffix}" if suffix else "")
        self.connection.execute(
            "INSERT INTO edges VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (identifier, source, target, kind, table, record, observed_at or None, _json(attributes)),
        )


def _applications(store, writer):
    for row in store.records("applications"):
        app = writer.node("app:" + row["app_id"], "Application", app_id=row["app_id"])
        when = row["applied_at"]

        def link(identifier, node_kind, edge_kind, suffix="", **attributes):
            writer.node(identifier, node_kind)
            writer.edge(app, identifier, edge_kind, "applications", row["app_id"], when,
                        suffix=suffix, **attributes)

        wallet = normalize.account("momo_wallet", "", row["phone"])
        link(wallet, "Account", "HAS_WALLET")
        if row.get("cccd"):
            link("person:" + row["cccd"].strip(), "Person", "APPLIED_BY")
        if row["device_id"]:
            link("device:" + row["device_id"], "Device", "USES_DEVICE")
        for position in ("ref1", "ref2"):
            if row.get(position + "_phone"):
                link("phone:" + normalize.phone(row[position + "_phone"]), "Phone", "REFERENCE",
                     suffix=position, relation=row.get(position + "_relation", ""))
        if row.get("ip_type") in {"vpn", "datacenter"} and row.get("ip"):
            link("ipblock:" + normalize.ip_block(row["ip"]), "IpBlock", "FROM_IP",
                 ip_type=row["ip_type"])
        if row.get("sim_age_days") and 0 <= int(row["sim_age_days"]) < 30:
            link("simblock:" + normalize.phone(row["phone"])[:8], "SimBlock", "SIM_IN")


def _transfers(store, writer):
    for row in store.records("wallet_transfers"):
        matches = store.connection.execute(
            "SELECT payload FROM applications WHERE wallet = ?", (normalize.phone(row["from_wallet"]),)
        ).fetchall()
        if len(matches) != 1:
            raise ValueError(f"Transfer {row['transfer_id']} must match exactly one application")
        application = json.loads(matches[0]["payload"])
        if not application["disbursed_at"]:
            raise ValueError(f"Transfer {row['transfer_id']} has no disbursement")
        minutes = (datetime.fromisoformat(row["created_at"]) -
                   datetime.fromisoformat(application["disbursed_at"])).total_seconds() / 60
        amount, loan = int(row["amount"]), int(application["amount"])
        if minutes < 0 or amount <= 0 or loan <= 0:
            raise ValueError(f"Invalid transfer timing or amount: {row['transfer_id']}")
        resolved = True
        try:
            recipient_id = normalize.account(row["to_type"], row["to_bank"], row["to_id"])
        except ValueError:
            resolved = False
            recipient_id = "unresolved:" + row["transfer_id"]
            store.connection.execute(
                "INSERT INTO quality_issues VALUES (?, ?)",
                (row["transfer_id"], "invalid_recipient_identity"),
            )
        account = writer.node(recipient_id, "Account" if resolved else "UnresolvedAccount")
        writer.edge(
            "app:" + application["app_id"], account, "SENT_TO", "wallet_transfers",
            row["transfer_id"], row["created_at"], amount=amount,
            recipient_resolved=resolved,
            minutes_after_disbursal=minutes, pct_of_loan=amount / loan * 100,
            to_name=row.get("to_name", ""), note=row.get("note", ""),
            recipient_in_contacts=normalize.flag(row.get("recipient_in_contacts", ""))
                if "recipient_in_contacts" in row else None,
            prior_transfers_to_recipient=int(row["prior_transfers_to_recipient"])
                if row.get("prior_transfers_to_recipient") else None,
            contact_saved_minutes_ago=int(row["contact_saved_minutes_ago"])
                if row.get("contact_saved_minutes_ago") else None,
            simo_flag=normalize.flag(row["simo_flag"]) if "simo_flag" in row else None,
            to_is_merchant=normalize.flag(row["to_is_merchant"]) if "to_is_merchant" in row else None,
        )
        if resolved and row["to_type"] == "momo_wallet" and row.get("to_wallet_opened_device"):
            device = writer.node("device:" + row["to_wallet_opened_device"], "Device")
            writer.edge(account, device, "OPENED_ON", "wallet_transfers", row["transfer_id"],
                        row["created_at"], wallet_age_days=int(row["to_wallet_age_days"])
                        if row.get("to_wallet_age_days") else None)


def _reports(store, writer):
    for row in store.records("scam_reports"):
        report = writer.node("report:" + row["report_id"], "Report", report_id=row["report_id"])
        if row["reporter_phone"]:
            wallet = writer.node(normalize.account("momo_wallet", "", row["reporter_phone"]), "Account")
            writer.edge(report, wallet, "REPORTED_BY", "scam_reports", row["report_id"], row["reported_at"])


def build_graph(data_dir: str | Path, database: str | Path, *, replace: bool = False) -> dict:
    directory, database = Path(data_dir), Path(database)
    for table in TABLES:
        if not (directory / f"{table}.csv").is_file():
            raise FileNotFoundError(directory / f"{table}.csv")
    database.parent.mkdir(parents=True, exist_ok=True)
    with GraphStore(database) as store:
        with store.connection:
            if any(store.connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                   for table in (*TABLES, "nodes", "edges", "quality_issues")):
                if not replace:
                    raise FileExistsError("Graph database already contains data; use replace=True to rebuild")
                for table in ("edges", "nodes", "quality_issues", *TABLES):
                    store.connection.execute(f"DELETE FROM {table}")
            _import_csv(store, directory)
            writer = _Writer(store)
            _applications(store, writer)
            _transfers(store, writer)
            _reports(store, writer)
        return store.stats()
