from app.tools.cluster_summary import summarize_money
from .transactions import transaction_rows, transaction_view
from .loans import applications_at


def cluster_money_flow(context, ids, *, limit=20, offset=0):
    reports = [dict(r, record_id="reports:" + r["report_id"]) for r in context.reports()]
    transfers = []
    for row in transaction_rows(context, ids):
        item = transaction_view(context, row, reports)
        transfers.append(item)
    applications = [{"app_id": row["app_id"], "amount": row["amount"], "record_id": row["loan_record_id"]}
                    for row in applications_at(context, ids)]
    return summarize_money(applications, transfers, reports, cluster_id=context.alert["cluster_id"], limit=limit, offset=offset,
        coverage={"as_of": context.cutoff, "scope_complete": set(ids) == set(context.ids),
                  "cohort_truncated": context.alert.get("context",{}).get("scope_truncated",False),
                  "loan_scope": "Latest disbursement through as_of, or the triggering transfer's explicit loan binding; held attempts excluded from outflow totals.",
                  "report_analysis": "Stored backend annotations; each report includes annotation_mode and match_basis."})
