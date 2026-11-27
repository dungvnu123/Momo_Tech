"""Create a consistent backend snapshot without importing mock AI or labels."""
import csv
import hashlib
import json
import re
from pathlib import Path

from app import db


def select_groups(connection, request):
    rows = connection.execute(
        "SELECT cid,app_ids,priority,signals FROM alerts WHERE latest AND cid IS NOT NULL "
        "ORDER BY priority DESC,cid,alert_id"
    ).fetchall()
    eligible, seen = [], set()
    for row in rows:
        ids = json.loads(row["app_ids"])
        if row["cid"] in seen or not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids):
            continue
        seen.add(row["cid"])
        eligible.append({"cluster_id": row["cid"], "app_ids": ids, "signals": json.loads(row["signals"])})
    if request.cluster_ids:
        by_id = {g["cluster_id"]: g for g in eligible}
        if len(set(request.cluster_ids)) != len(request.cluster_ids) or not set(request.cluster_ids) <= by_id.keys():
            raise ValueError("Unknown, oversized or duplicate candidate clusters")
        selected = [by_id[identifier] for identifier in request.cluster_ids[:request.cluster_limit]]
    else:
        # Include both ends of the queue, then different signal combinations.
        selected = eligible[:1]
        if len(eligible) > 1 and request.cluster_limit > 1:
            selected.append(eligible[-1])
        signatures = {tuple(sorted(g["signals"])) for g in selected}
        for group in eligible:
            signature = tuple(sorted(group["signals"]))
            if len(selected) < request.cluster_limit and signature not in signatures:
                selected.append(group)
                signatures.add(signature)
        for group in eligible:
            if len(selected) < request.cluster_limit and group not in selected:
                selected.append(group)
    return [{"cluster_id": g["cluster_id"], "app_ids": g["app_ids"]} for g in selected], len(eligible)


def select_reports(connection, groups, limit):
    ids = sorted({identifier for group in groups for identifier in group["app_ids"]})
    wallets, recipients = set(), set()
    if ids:
        rows = connection.execute("SELECT phone FROM apps WHERE app_id IN (" + ",".join("?" for _ in ids) + ")", ids)
        wallets = {row[0] for row in rows}
    if wallets:
        rows = connection.execute("SELECT to_id FROM transfers WHERE from_wallet IN (" + ",".join("?" for _ in wallets) + ")", sorted(wallets))
        recipients = {row[0] for row in rows}
    ranked = []
    for row in connection.execute("SELECT report_id,reporter_phone,raw_text,reported_at FROM reports"):
        # Coarse blocking only; verdicts/indicators are produced by the LLM later.
        text = re.sub(r"[\s.\-]", "", row["raw_text"]).replace("o", "0").replace("O", "0")
        score = 2 * (row["reporter_phone"] in wallets) + any(value and value in text for value in recipients)
        ranked.append((-score, row["reported_at"], row["report_id"]))
    return [item[2] for item in sorted(ranked)[:limit]]


def export_backend(database, directory, request):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    counts, hashes = {}, {}
    connection = db.connect(database, read_only=True)
    try:
        # 1 ảnh chụp nhất quán cho toàn bộ lần xuất (thay cho BEGIN trên file SQLite chỉ đọc)
        connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        groups, eligible = select_groups(connection, request)
        report_ids = select_reports(connection, groups, request.report_limit)
        for table, output, excluded in (("apps", "applications", {"signals"}),
                                        ("transfers", "wallet_transfers", set()),
                                        ("reports", "scam_reports", {"analysis"})):
            columns = [name for name in db.table_columns(connection, table) if name not in excluded]
            if not columns or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in columns):
                raise ValueError("Unexpected backend source schema")
            path = directory / (output + ".csv")
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(columns)
                count = 0
                for row in connection.execute(f"SELECT {','.join(columns)} FROM {table}"):
                    writer.writerow(tuple(row))
                    count += 1
            counts[output] = count
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            hashes[output] = digest.hexdigest()
        connection.execute("COMMIT")
    finally:
        connection.close()
    return {"counts": counts, "source_hashes": hashes, "groups": groups, "report_ids": report_ids,
            "eligible_clusters": eligible, "selection": "priority_and_signal_diversity_without_labels",
            "time_scope": "complete_backend_snapshot_not_historical_alert_replay"}
