from app.graph import GraphStore

from ..schemas import EvidenceInput
from ..views import GraphViews


def get_evidence(store: GraphStore, request: EvidenceInput, views: GraphViews) -> dict:
    edge = store.edge(request.edge_id)
    evidence = store.source_record(request.edge_id)
    record = evidence["record"]
    if evidence["table"] == "applications":
        record = views.application(record)
    elif evidence["table"] == "wallet_transfers":
        record = views.transfer(record)
    elif evidence["table"] == "ai_report_analysis":
        from .reports import analysis_view
        record = analysis_view(record)
    elif evidence["table"] == "ai_entity_decisions":
        from .entities import decision_view
        record = decision_view(store, record)
    elif evidence["table"] == "live_loans":
        record = {k: record[k] for k in ("loan_id", "amount", "disbursed_at")}
    else:
        record = views.report(record)
    return {"edge": views.edge(edge), "source_table": evidence["table"], "record": record}
