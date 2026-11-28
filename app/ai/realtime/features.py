from collections import Counter
from datetime import datetime
from statistics import median

from app.ai.triage.schemas import ClusterSummary
from app.backend.agent_tools import BackendAgentTools
from app.backend.evidence.cluster_money import cluster_money_flow
from app.backend.evidence.loans import applications_at


def summarize(store, alert, *, truncated=False):
    tools = BackendAgentTools(store, alert)
    apps = applications_at(tools, tools.ids)
    flow = cluster_money_flow(tools, tools.ids)
    count = len(apps)
    devices = Counter(a.get("device_id") for a in apps if a.get("device_id"))
    references = Counter({})
    for a in apps:
        references.update({p for p in (a.get("ref1_phone"), a.get("ref2_phone")) if p})
    times = [datetime.fromisoformat(a["applied_at"]) for a in apps]
    fills = [float(a["fill_time_sec"]) for a in apps if a.get("fill_time_sec") not in (None, "")]
    summary = ClusterSummary(
        cluster_id=alert["cluster_id"],
        app_ids=tools.ids,
        size=count,
        applied_span_hours=(max(times) - min(times)).total_seconds() / 3600,
        new_sim_ratio=sum(int(a.get("sim_age_days") or 99999) < 30 for a in apps) / count,
        vpn_ratio=sum(a.get("ip_type") in {"vpn", "datacenter"} for a in apps) / count,
        emulator_ratio=sum(str(a.get("is_emulator")).lower() == "true" for a in apps) / count,
        suspicious_ekyc_ratio=None,
        median_fill_time_sec=median(fills) if fills else None,
        rapid_outflow_ratio=sum(
            a["total_amount"] >= 0.8 * a["loan_amount"] for a in flow["application_summaries"]
        )
        / count,
        stranger_outflow_ratio=flow["totals"]["rapid_stranger_applications"] / count,
        shared_device_count=sum(n > 1 for n in devices.values()),
        max_device_applications=max(devices.values(), default=0),
        max_reference_applications=max(references.values(), default=0),
        shared_recipient_count=flow["totals"]["shared_recipient_count"],
        reported_recipient_count=sum(bool(r["report_ids"]) for r in flow["recipients"]),
        self_report_count=sum(a["victim_self_report_count"] for a in flow["application_summaries"]),
        median_dpd=None,
        note=f"Backend snapshot at alert time; held attempts={flow['totals']['held_transfer_count']}; "
        f"scope_truncated={truncated}; reports are unverified backend annotations; eKYC/delinquency not fully evaluated.",
    )
    relevant = bool(
        flow["totals"]["held_transfer_count"]
        or summary.stranger_outflow_ratio
        or summary.shared_recipient_count
        or summary.reported_recipient_count
        or summary.self_report_count
        or summary.max_device_applications >= 2
        or summary.max_reference_applications >= 2
        or summary.emulator_ratio
        or (summary.vpn_ratio and summary.new_sim_ratio)
    )
    return summary, relevant
