"""Bounded, masked reads of the backend snapshot at the alert's timestamp."""
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .evidence.reports import report_views
from .evidence.transactions import money_flow, transaction_rows, transaction_view
from .evidence.validation import validate_case


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str | None = Field(default=None, max_length=64)
    app_ids: list[str] | None = Field(default=None, max_length=100)
    cluster_id: str | None = Field(default=None, max_length=64)
    node_id: str | None = Field(default=None, max_length=64)
    transfer_id: str | None = Field(default=None, max_length=64)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=50)


class BackendAgentTools:
    parameter_fields = {
        "get_cluster": ("cluster_id",), "get_application": ("app_id",),
        "tech_profile": ("app_ids",), "money_flow": ("app_ids", "offset", "limit"),
        "reports_mentioning": ("offset", "limit"), "account_senders": ("node_id", "offset", "limit"),
        "timeline": ("app_id",), "get_transfer": ("transfer_id",),
    }
    descriptions = {
        "get_cluster": "Read the alert snapshot, scoped application IDs and signals. No arguments needed.",
        "get_application": "Read safe application fields; supply app_id from the snapshot.",
        "tech_profile": "Read aggregate technical signals for app_ids, or the snapshot by default.",
        "money_flow": "Read masked transfers up to the alert time for app_ids, or the snapshot by default.",
        "reports_mentioning": "Read report assessments and victim attribution for the snapshot, up to the alert time. No arguments needed.",
        "account_senders": "Read senders up to the alert time for an opaque recipient node_id from money_flow.",
        "timeline": "Read event timestamps and types up to the alert time for app_id.",
        "get_transfer": "Read a transfer_id, especially triggering_transfer_id from get_cluster: SIMO, report links, recipient context and amount relative to loan.",
    }

    def __init__(self, store, alert):
        self.store, self.alert = store, alert
        self.cutoff = alert["ts"]
        self.ids = [r["app_id"] for r in store.apps(alert["app_ids"])
                    if r["applied_at"] <= self.cutoff]
        self.tokens = {}
        self.readable_ids = set(self.ids)

    @property
    def definitions(self):
        result = []
        for name, description in self.descriptions.items():
            schema = Arguments.model_json_schema()
            schema["properties"] = {k: v for k, v in schema["properties"].items() if k in self.parameter_fields[name]}
            if name in {"get_application", "timeline", "account_senders", "get_transfer"}:
                schema["required"] = list(self.parameter_fields[name])
            result.append({"name": name, "description": description, "parameters": schema})
        return result

    def token(self, value):
        if value not in self.tokens:
            self.tokens[value] = "recipient_" + uuid4().hex
        return self.tokens[value]

    def reports(self):
        return report_views(self)

    def validate_case(self, case, steps):
        validate_case(self, case, steps)

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
            if not set(ids) <= self.readable_ids:
                raise ValueError("Outside snapshot")
            if args.app_id and args.app_id not in self.readable_ids:
                raise ValueError("Outside snapshot")
            if name == "get_cluster":
                data = {"cluster_id": self.alert["cluster_id"], "app_ids": self.ids[:100],
                        "size": len(self.ids), "signals": self.alert["signals"],
                        "alert_kind": self.alert.get("kind"), "alert_id": self.alert["alert_id"],
                        "triggering_transfer_id": self.alert.get("transfer_id"),
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
                data = money_flow(self, ids, self.reports(), args.offset, args.limit)
            elif name == "get_transfer":
                transfer = next(t for t in transaction_rows(self, sorted(self.readable_ids)) if t["transfer_id"] == args.transfer_id)
                data = {"transfer": transaction_view(self, transfer, self.reports())}
            elif name == "reports_mentioning":
                reports = self.reports()
                data = {"reports": reports[args.offset:args.offset + args.limit], "total": len(reports),
                        "truncated": args.offset + args.limit < len(reports),
                        "next_offset": args.offset + args.limit if args.offset + args.limit < len(reports) else None,
                        "coverage": "Stored report assessments; annotation_mode identifies simulated annotations."}
            elif name == "account_senders":
                kind, bank, account = next(k for k, v in self.tokens.items() if v == args.node_id)
                rows = self.store.q("SELECT a.app_id, t.created_at, t.amount FROM transfers t "
                                    "JOIN apps a ON a.phone=t.from_wallet WHERE t.to_id=? "
                                    "AND t.to_type=? AND (?='' OR UPPER(t.to_bank)=?) "
                                    "AND t.created_at <= ? AND a.applied_at <= ? ORDER BY t.created_at,t.transfer_id LIMIT ? OFFSET ?",
                                    account, kind, bank, bank, self.cutoff, self.cutoff, args.limit + 1, args.offset)
                discovered = {r["app_id"] for r in rows[:args.limit]}
                self.readable_ids.update(sorted(discovered - self.readable_ids)[:max(0, 100 - len(self.readable_ids))])
                data = {"senders": rows[:args.limit], "app_ids": sorted(discovered),
                        "truncated": len(rows) > args.limit,
                        "next_offset": args.offset + args.limit if len(rows) > args.limit else None,
                        "readable_app_ids": sorted(self.readable_ids)[:100]}
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
