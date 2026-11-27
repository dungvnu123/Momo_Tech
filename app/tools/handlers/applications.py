from app.graph.ai_store import AIStore
from app.graph.normalize import phone

from ..schemas import ApplicationInput
from ..views import GraphViews
from .common import _app_id


def get_application(store: AIStore, request: ApplicationInput, views: GraphViews) -> dict:
    identifier = _app_id(request.app_id)
    record = store.application(identifier)
    return {"node_id": "app:" + identifier, "application": views.application(record),
            "victim_self_report_count": store.self_reports("account:momo:" + phone(record["phone"]))}
