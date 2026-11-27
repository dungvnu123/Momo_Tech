from app.graph import GraphStore

from ..schemas import NeighborsInput
from ..views import GraphViews


def neighbors(store: GraphStore, request: NeighborsInput, views: GraphViews) -> dict:
    identifier = views.resolve(request.node_id)
    page = store.related_edges(identifier, edge_type=request.edge_type, direction=request.direction,
                               limit=request.limit, offset=request.offset)
    node_ids = {identifier}
    for edge in page["edges"]:
        node_ids.update((edge["source"], edge["target"]))
    return {
        "node_id": views.public_id(identifier),
        "nodes": [views.node(store, node) for node in sorted(node_ids)],
        "edges": [views.edge(edge) for edge in page["edges"]],
        "returned_count": len(page["edges"]), "truncated": page["truncated"],
        "next_offset": page["next_offset"],
    }
