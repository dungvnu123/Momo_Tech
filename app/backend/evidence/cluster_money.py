from app.tools.cluster_summary import summarize_money
from .transactions import transaction_rows, transaction_view


def cluster_money_flow(context, ids, *, limit=20, offset=0):
    reports = [dict(r, record_id="reports:" + r["report_id"]) for r in context.reports()]
    transfers = []
    for row in transaction_rows(context, ids):
        item = transaction_view(context, row, reports)
        item["record_id"] = "transfers:" + item["transfer_id"]
        transfers.append(item)
    applications = [{"app_id": row["app_id"], "amount": row["amount"], "record_id": "apps:" + row["app_id"]}
                    for row in context.store.apps(ids)]
    return summarize_money(applications, transfers, reports, cluster_id=context.alert["cluster_id"], limit=limit, offset=offset,
        coverage={"as_of": context.cutoff, "scope_complete": set(ids) == set(context.ids),
                  "report_analysis": "Stored backend annotations; each report includes annotation_mode and match_basis."})
