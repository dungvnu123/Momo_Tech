from collections import Counter, defaultdict
from datetime import datetime
from statistics import median

from app.graph.normalize import flag, name_match, phone

from .schemas import ClusterSummary


def cluster_summary(store, cluster_id, app_ids):
    if not 1 <= len(app_ids) <= 100 or len(set(app_ids)) != len(app_ids):
        raise ValueError("Expected 1..100 distinct application IDs")
    rows = [store.latest_application_loan(identifier) for identifier in app_ids]
    rapid = stranger = self_reports = 0
    devices, recipients, reported = Counter(), defaultdict(set), set()
    references, identities = defaultdict(set), defaultdict(set)
    wallet_ids = {"account:momo:" + phone(row["phone"]) for row in rows}
    for row in rows:
        for key in ("ref1_phone", "ref2_phone"):
            if row.get(key):
                references[phone(row[key])].add(row["app_id"])
        if store.has_table("ai_entity_members"):
            entity = store.connection.execute("SELECT entity_id FROM ai_entity_members WHERE app_id=?", (row["app_id"],)).fetchone()
            if entity and row.get("cccd"):
                identities[entity[0]].add(row["cccd"])
        if row.get("device_id"):
            devices[row["device_id"]] += 1
        total = other = 0
        for edge in store.application_transfers(row["app_id"]):
            values = edge["attributes"]
            if values.get("loan_id") != row["loan_id"]:
                continue
            if values["minutes_after_disbursal"] <= 120:
                total += values["amount"]
                if name_match(row.get("full_name", ""), values.get("to_name", "")) is False:
                    other += values["amount"]
                if (values.get("recipient_resolved") and not values.get("to_is_merchant")
                        and values["pct_of_loan"] >= 30 and edge["target"] not in wallet_ids):
                    recipients[edge["target"]].add(row["app_id"])
            if store.connection.execute(
                "SELECT 1 FROM edges WHERE target=? AND kind='MENTIONS' "
                "AND payload::jsonb->>'verdict' IN ('scam', 'suspicious') LIMIT 1", (edge["target"],),
            ).fetchone():
                reported.add(edge["target"])
        loan = int(row["amount"])
        rapid += total >= 0.8 * loan
        stranger += other >= 0.8 * loan
        self_reports += store.self_reports("account:momo:" + phone(row["phone"]))
    count = len(rows)
    times = [datetime.fromisoformat(row["applied_at"]) for row in rows]
    numeric = lambda key: [float(row[key]) for row in rows if row.get(key) not in (None, "")]
    ekyc = [row for row in rows if row.get("device_first_seen_hours") not in (None, "")]
    suspicious = sum(float(row["device_first_seen_hours"]) < 24 or flag(row.get("is_rooted_or_hooked", ""))
                     or float(row.get("liveness_score", 1)) < 0.85 or int(row.get("ekyc_attempts", 1)) >= 3 for row in ekyc)
    notes = []
    if not ekyc:
        notes.append("eKYC detail unavailable")
    coverage = store.report_coverage()
    if not coverage["complete"]:
        notes.append(f"report coverage {coverage['indexed']}/{coverage['total']}; zero reports is not evidence of safety")
    return ClusterSummary(
        cluster_id=cluster_id, app_ids=app_ids, size=count,
        applied_span_hours=(max(times) - min(times)).total_seconds() / 3600,
        new_sim_ratio=sum(int(row.get("sim_age_days") or 99999) < 30 for row in rows) / count,
        vpn_ratio=sum(row.get("ip_type") in {"vpn", "datacenter"} for row in rows) / count,
        emulator_ratio=sum(flag(row.get("is_emulator", "")) for row in rows) / count,
        suspicious_ekyc_ratio=suspicious / len(ekyc) if ekyc else None,
        median_fill_time_sec=median(numeric("fill_time_sec")) if numeric("fill_time_sec") else None,
        rapid_outflow_ratio=rapid / count, stranger_outflow_ratio=stranger / count,
        shared_device_count=sum(value >= 2 for value in devices.values()),
        max_device_applications=max(devices.values(), default=0),
        max_reference_applications=max((len(value) for value in references.values()), default=0),
        same_person_multiple_identity_count=sum(len(value) > 1 for value in identities.values()),
        shared_recipient_count=sum(len(value) >= 2 for value in recipients.values()),
        reported_recipient_count=len(reported), self_report_count=self_reports,
        median_dpd=median(numeric("dpd")) if numeric("dpd") else None, note="; ".join(notes),
    )
