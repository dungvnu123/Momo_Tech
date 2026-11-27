from app.graph import GraphStore

from ..schemas import MoneyFlowInput
from ..views import GraphViews, name_match
from .common import _app_id


def money_flow(store: GraphStore, request: MoneyFlowInput, views: GraphViews) -> dict:
    identifier = _app_id(request.app_id)
    summary = store.money_summary(identifier)
    application = store.application(identifier)
    page = store.related_edges("app:" + identifier, edge_type="SENT_TO", direction="outgoing",
                               limit=request.limit, offset=request.offset)
    transfers = []
    for edge in page["edges"]:
        transfer = views.edge(edge)
        transfer["attributes"]["recipient_name_matches_applicant"] = name_match(
            application.get("full_name", ""), edge["attributes"].get("to_name", ""),
        )
        transfers.append(transfer)
    return {
        "app_id": identifier, **summary,
        "transfers": transfers,
        "returned_count": len(page["edges"]), "truncated": page["truncated"],
        "next_offset": page["next_offset"],
    }


def account_senders(store, request, views):
    identifier = views.resolve(request.node_id)
    if store.node(identifier)["kind"] != "Account":
        raise ValueError("Expected a resolved account")
    page = store.related_edges(identifier, edge_type="SENT_TO", direction="incoming",
                               limit=request.limit, offset=request.offset)
    return {"node_id": views.public_id(identifier),
            "app_ids": sorted({edge["source"].removeprefix("app:") for edge in page["edges"]}),
            "transfers": [views.edge(edge) for edge in page["edges"]],
            "returned_count": len(page["edges"]), "truncated": page["truncated"], "next_offset": page["next_offset"]}
