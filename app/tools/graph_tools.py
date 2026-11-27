from app import db
from pathlib import Path

from pydantic import ValidationError

from app.graph.ai_store import AIStore

from .handlers import HANDLERS
from .schemas import DESCRIPTIONS, INPUTS, ToolError, ToolResponse
from .views import GraphViews


class GraphTools:
    def __init__(self, database: str | Path = "data/graph.db") -> None:
        self.database = Path(database).resolve()
        self._views = GraphViews()

    @property
    def definitions(self) -> list[dict]:
        return [{"name": name, "description": DESCRIPTIONS[name], "parameters": model.model_json_schema()}
                for name, model in INPUTS.items()]

    def assessment_scope(self, app_id, cluster_id=None):
        with AIStore(self.database, read_only=True) as store:
            if cluster_id:
                record = store.ai_record("ai_clusters", cluster_id)
                if record is None:
                    raise ValueError("Requested cluster is unavailable")
                return record["summary"]["app_ids"]
            store.application(app_id)
        return [app_id]

    def call(self, name: str, arguments: dict) -> dict:
        if name not in INPUTS:
            return self._error(name, "unknown_tool", "Tool is not registered")
        try:
            request = INPUTS[name].model_validate(arguments)
        except ValidationError:
            return self._error(name, "invalid_arguments", "Arguments do not match the tool schema")
        try:
            with AIStore(self.database, read_only=True) as store:
                handler = HANDLERS[name]
                data = handler(store, request, self._views)
            return ToolResponse(ok=True, tool=name, data=data).model_dump(exclude_none=True)
        except KeyError:
            return self._error(name, "not_found", "Requested object was not found")
        except (FileNotFoundError, db.Error):
            return self._error(name, "storage_unavailable", "Graph database is unavailable")
        except (ValueError, TypeError):
            return self._error(name, "invalid_data", "Stored data could not be read")

    @staticmethod
    def _error(name, code, message):
        return ToolResponse(ok=False, tool=name, error=ToolError(code=code, message=message)).model_dump(exclude_none=True)

    def get_application(self, app_id: str) -> dict:
        return self.call("get_application", {"app_id": app_id})

    def neighbors(self, node_id: str, *, edge_type=None, direction="both", limit=20, offset=0) -> dict:
        return self.call("neighbors", {"node_id": node_id, "edge_type": edge_type,
                                      "direction": direction, "limit": limit, "offset": offset})

    def money_flow(self, app_id: str, *, limit=20, offset=0) -> dict:
        return self.call("money_flow", {"app_id": app_id, "limit": limit, "offset": offset})

    def cluster_money_flow(self, *, cluster_id=None, app_ids=None, limit=20, offset=0):
        return self.call("cluster_money_flow", {"cluster_id": cluster_id, "app_ids": app_ids or [],
                                                "limit": limit, "offset": offset})

    def get_evidence(self, edge_id: str) -> dict:
        return self.call("get_evidence", {"edge_id": edge_id})

    def get_cluster(self, cluster_id: str) -> dict:
        return self.call("get_cluster", {"cluster_id": cluster_id})

    def account_senders(self, node_id: str, *, limit=20, offset=0) -> dict:
        return self.call("account_senders", {"node_id": node_id, "limit": limit, "offset": offset})

    def reports_mentioning(self, node_id: str, *, limit=20, offset=0) -> dict:
        return self.call("reports_mentioning", {"node_id": node_id, "limit": limit, "offset": offset})

    def timeline(self, app_ids: list[str]) -> dict:
        return self.call("timeline", {"app_ids": app_ids})

    def tech_profile(self, app_ids: list[str]) -> dict:
        return self.call("tech_profile", {"app_ids": app_ids})

    def entity_info(self, node_id: str) -> dict:
        return self.call("entity_info", {"node_id": node_id})
