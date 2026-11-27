from uuid import uuid4

from app.graph.normalize import name_match

APPLICATION_FIELDS = {
    "app_id", "applied_at", "disbursed_at", "status", "amount", "dpd", "carrier", "device_os",
    "ip_type", "ip_province", "sim_age_days", "is_emulator", "fill_time_sec", "wallet_age_days",
    "device_first_seen_hours", "is_rooted_or_hooked", "liveness_score", "ekyc_attempts",
    "ref1_relation", "ref2_relation",
}
TRANSFER_FIELDS = {
    "transfer_id", "created_at", "to_type", "to_bank", "amount", "to_wallet_age_days",
    "recipient_in_contacts", "contact_saved_minutes_ago", "prior_transfers_to_recipient",
    "simo_flag", "to_is_merchant",
}
EDGE_FIELDS = {
    "relation", "ip_type", "amount", "recipient_resolved", "minutes_after_disbursal",
    "pct_of_loan", "recipient_in_contacts", "prior_transfers_to_recipient",
    "contact_saved_minutes_ago", "simo_flag", "to_is_merchant", "wallet_age_days",
    "ai_generated", "verdict", "confidence", "reporter_is_victim",
}


def _mask(value: str) -> str:
    value = "".join(character for character in value if character.isdigit())
    if len(value) <= 4:
        return "*" * len(value)
    start = (len(value) - 4) // 2
    return value[:start] + "****" + value[start + 4:]


class GraphViews:
    def __init__(self) -> None:
        self._aliases: dict[str, str] = {}
        self._identifiers: dict[str, str] = {}

    def public_id(self, identifier):
        if identifier.startswith(("app:", "report:", "unresolved:")):
            return identifier
        if identifier not in self._aliases:
            alias = "node:" + uuid4().hex
            self._aliases[identifier] = alias
            self._identifiers[alias] = identifier
        return self._aliases[identifier]

    def resolve(self, identifier):
        if identifier.startswith("node:"):
            return self._identifiers[identifier]
        return identifier

    def node(self, store, identifier):
        node = store.node(identifier)
        return {"node_id": self.public_id(identifier), "kind": node["kind"]}

    def edge(self, edge):
        return {
            "edge_id": edge["id"], "source": self.public_id(edge["source"]),
            "target": self.public_id(edge["target"]), "kind": edge["kind"],
            "source_table": edge["source_table"], "source_id": edge["source_id"],
            "observed_at": edge["observed_at"],
            "attributes": {key: value for key, value in edge["attributes"].items() if key in EDGE_FIELDS},
        }

    def application(self, record):
        result = {key: value for key, value in record.items() if key in APPLICATION_FIELDS}
        for key in ("phone", "cccd", "ref1_phone", "ref2_phone"):
            if key in record:
                result[key] = _mask(record[key])
        if record.get("device_id"):
            result["device_node_id"] = self.public_id("device:" + record["device_id"])
        return result

    def transfer(self, record):
        result = {key: value for key, value in record.items() if key in TRANSFER_FIELDS}
        for key in ("from_wallet", "to_id"):
            if key in record:
                result[key] = _mask(record[key])
        return result

    def report(self, record):
        result = {key: value for key, value in record.items()
                  if key in {"report_id", "reported_at", "channel"}}
        result["reporter_phone"] = _mask(record.get("reporter_phone", ""))
        result["raw_text_omitted"] = True
        return result

