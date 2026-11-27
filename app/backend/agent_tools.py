"""Bounded, masked reads of the backend snapshot at the alert's timestamp."""
import json
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str | None = Field(default=None, max_length=64)
    app_ids: list[str] | None = Field(default=None, max_length=100)
    cluster_id: str | None = Field(default=None, max_length=64)
    node_id: str | None = Field(default=None, max_length=64)


class BackendAgentTools:
    parameter_fields = {
        "get_cluster": ("cluster_id",), "get_application": ("app_id",),
        "tech_profile": ("app_ids",), "money_flow": ("app_ids",),
        "reports_mentioning": (), "account_senders": ("node_id",), "timeline": ("app_id",),
    }
    descriptions = {
        "get_cluster": "Read the alert snapshot, scoped application IDs and signals. No arguments needed.",
        "get_application": "Read safe application fields; supply app_id from the snapshot.",
        "tech_profile": "Read aggregate technical signals for app_ids, or the snapshot by default.",
        "money_flow": "Read masked transfers up to the alert time for app_ids, or the snapshot by default.",
        "reports_mentioning": "Read report assessments and victim attribution for the snapshot, up to the alert time. No arguments needed.",
        "account_senders": "Read senders up to the alert time for an opaque recipient node_id from money_flow.",
        "timeline": "Read event timestamps and types up to the alert time for app_id.",
    }

    def __init__(self, store, alert):
        self.store, self.alert = store, alert
        self.cutoff = alert["ts"]
        self.ids = [r["app_id"] for r in store.apps(alert["app_ids"])
                    if r["applied_at"] <= self.cutoff]
        self.tokens = {}

    @property
    def definitions(self):
        result = []
        for name, description in self.descriptions.items():
            schema = Arguments.model_json_schema()
            schema["properties"] = {k: v for k, v in schema["properties"].items() if k in self.parameter_fields[name]}
            if name in {"get_application", "timeline", "account_senders"}:
                schema["required"] = list(self.parameter_fields[name])
            result.append({"name": name, "description": description, "parameters": schema})
        return result

    def token(self, value):
        if value not in self.tokens:
            self.tokens[value] = "recipient_" + uuid4().hex
        return self.tokens[value]

    def reports(self):
        rows = self.store.apps(self.ids)
        wallets = {r["phone"] for r in rows}
        recipients = set(self.store.money_flow(self.ids, self.cutoff)["recipients"])
        reports = []
        for row in self.store.q("SELECT * FROM reports WHERE reported_at <= ? ORDER BY reported_at", self.cutoff):
            analysis = json.loads(row["analysis"])
            indicators = analysis["indicators"]
            if not (set(indicators["accounts"] + indicators["phones"]) & recipients
                    or row["reporter_phone"] in wallets):
                continue
            reporters = self.store.q("SELECT app_id FROM apps WHERE phone=? AND applied_at <= ?",
                                     row["reporter_phone"], self.cutoff)
            reports.append({"report_id": row["report_id"], "reported_at": row["reported_at"],
                            "verdict": analysis["verdict"],
                            "reporter_is_victim": analysis["reporter_is_victim"],
                            "reporter_app_ids": [r["app_id"] for r in reporters],
                            "annotation_mode": analysis.get("mode", "unknown")})
        return reports

    def call(self, name, arguments):
        try:
            if name not in self.descriptions:
                raise ValueError("Unknown tool")
            if not set(arguments) <= set(self.parameter_fields[name]):
                raise ValueError("Unexpected arguments")
            args = Arguments.model_validate(arguments)
            if args.app_id:
                args.app_id = args.app_id.removeprefix("app:")
            if args.app_ids:
                args.app_ids = [value.removeprefix("app:") for value in args.app_ids]
            if args.cluster_id and args.cluster_id != self.alert["cluster_id"]:
                raise ValueError("Outside snapshot")
            ids = args.app_ids if args.app_ids is not None else self.ids
            if not set(ids) <= set(self.ids):
                raise ValueError("Outside snapshot")
            if args.app_id and args.app_id not in self.ids:
                raise ValueError("Outside snapshot")
            if name == "get_cluster":
                data = {"cluster_id": self.alert["cluster_id"], "app_ids": self.ids[:100],
                        "size": len(self.ids), "signals": self.alert["signals"],
                        "as_of": self.cutoff, "truncated": len(self.ids) > 100}
            elif name == "get_application":
                row = self.store.apps([args.app_id])[0]
                fields = ("app_id", "amount", "applied_at", "ip_type", "sim_age_days", "fill_time_sec",
                          "is_emulator", "is_rooted_or_hooked", "device_first_seen_hours")
                data = {"application": {k: row[k] for k in fields},
                        "victim_self_report_count": sum(r["reporter_is_victim"] and args.app_id in r["reporter_app_ids"]
                                                        for r in self.reports())}
            elif name == "tech_profile":
                data = {"app_ids": ids[:100], **self.store.tech_profile(ids)}
            elif name == "money_flow":
                flow = self.store.money_flow(ids, self.cutoff)
                data = {k: flow[k] for k in ("fast_out_stranger", "summary")}
                data.update(app_ids=ids[:100], recipients=[self.token(v) for v in flow["recipients"][:50]],
                            shared_recipients={self.token(k): v[:100] for k, v in list(flow["shared_recipients"].items())[:50]},
                            transfers=[{"transfer_id": t["transfer_id"], "amount": t["amount"],
                                        "created_at": t["created_at"]} for t in flow["transfers"][:50]],
                            transfer_count=len(flow["transfers"]), truncated=len(flow["transfers"]) > 50,
                            recipient_count=len(flow["recipients"]))
            elif name == "reports_mentioning":
                reports = self.reports()
                data = {"reports": reports[:50], "total": len(reports), "truncated": len(reports) > 50,
                        "coverage": "Stored report assessments; annotation_mode identifies simulated annotations."}
            elif name == "account_senders":
                account = next(k for k, v in self.tokens.items() if v == args.node_id)
                rows = self.store.q("SELECT a.app_id, t.created_at, t.amount FROM transfers t "
                                    "JOIN apps a ON a.phone=t.from_wallet WHERE t.to_id=? "
                                    "AND t.created_at <= ? AND a.applied_at <= ? ORDER BY t.created_at LIMIT 51",
                                    account, self.cutoff, self.cutoff)
                data = {"senders": rows[:50], "app_ids": sorted({r["app_id"] for r in rows[:50]}),
                        "truncated": len(rows) > 50}
            else:
                timeline = self.store.timeline(args.app_id, self.cutoff)
                events = timeline["events"]
                data = {"app_id": args.app_id, "dpd": timeline["dpd"],
                        "events": [{"ts": e["ts"], "type": e["type"]} for e in events[:50]],
                        "truncated": len(events) > 50}
            # Include scoped victim evidence with every read so an offender
            # submission cannot bypass attribution by skipping the report tool.
            data.setdefault("reports", [r for r in self.reports() if r["reporter_is_victim"]][:50])
            return {"ok": True, "tool": name, "data": {**data, "as_of": self.cutoff}}
        except (ValidationError, ValueError, KeyError, IndexError, StopIteration, TypeError):
            return {"ok": False, "tool": name, "error": {"code": "invalid_snapshot_read"}}
