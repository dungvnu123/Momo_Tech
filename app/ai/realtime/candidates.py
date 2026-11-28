"""Discover a bounded cohort from backend even before a full graph has been built."""


def candidates(store, event, app, source):
    refs = [app[k] for k in ("ref1_phone", "ref2_phone") if app.get(k)]
    rows = store.q(
        "SELECT app_id FROM apps WHERE applied_at<=? AND "
        "(device_id=? OR ref1_phone=ANY(?) OR ref2_phone=ANY(?)) ORDER BY app_id LIMIT 101",
        event["occurred_at"],
        app.get("device_id"),
        refs,
        refs,
    )
    if app.get("ip_type") in {"vpn", "datacenter"} and app.get("ip"):
        rows += store.q(
            "SELECT app_id FROM apps WHERE applied_at<=? AND ip LIKE ? AND ip_type IN ('vpn','datacenter') "
            "ORDER BY app_id LIMIT 101",
            event["occurred_at"],
            app["ip"].rsplit(".", 1)[0] + ".%",
        )
    if app.get("sim_age_days") not in (None, "") and int(app["sim_age_days"]) < 30:
        rows += store.q(
            "SELECT app_id FROM apps WHERE applied_at<=? AND phone LIKE ? AND sim_age_days::integer<30 "
            "ORDER BY app_id LIMIT 101",
            event["occurred_at"],
            app["phone"][:8] + "%",
        )
    if event["kind"] == "transfer":
        params = [
            source["to_id"],
            source["to_type"],
            source["to_bank"].upper(),
            event["occurred_at"],
        ]
        rows += store.q(
            "SELECT DISTINCT a.app_id FROM transfers t JOIN apps a ON a.phone=t.from_wallet "
            "WHERE t.to_id=? AND t.to_type=? AND UPPER(t.to_bank)=? AND t.created_at<=? AND a.applied_at<=? "
            "ORDER BY a.app_id LIMIT 101",
            *params,
            event["occurred_at"],
        )
        rows += store.q(
            "SELECT DISTINCT a.app_id FROM khach_transfers t JOIN apps a ON a.phone=t.phone "
            "WHERE t.to_id=? AND t.to_type=? AND UPPER(t.to_bank)=? AND t.ts<=? AND a.applied_at<=? "
            "AND NOT EXISTS (SELECT 1 FROM ai_events e WHERE e.kind='transfer' AND e.source_id='KT'||t.tx_id::text AND e.sequence>?) "
            "ORDER BY a.app_id LIMIT 101",
            *params,
            event["occurred_at"],
            event["sequence"],
        )
    return {row["app_id"] for row in rows}
