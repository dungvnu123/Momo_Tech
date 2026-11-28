from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
EdgeType = Literal[
    "HAS_WALLET", "APPLIED_BY", "USES_DEVICE", "REFERENCE", "FROM_IP", "SIM_IN",
    "SENT_TO", "OPENED_ON", "REPORTED_BY",
    "MENTIONS", "RESOLVED_AS", "HOUSEHOLD_CANDIDATE",
    "HAS_LOAN", "TRANSFER_ATTEMPT",
]


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ApplicationInput(ToolInput):
    app_id: Identifier


class PageInput(ToolInput):
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=100000)


class NeighborsInput(PageInput):
    node_id: Identifier
    edge_type: EdgeType | None = None
    direction: Literal["both", "incoming", "outgoing"] = "both"


class MoneyFlowInput(PageInput):
    app_id: Identifier


class EvidenceInput(ToolInput):
    edge_id: Identifier


class NodeInput(PageInput):
    node_id: Identifier


class ClusterInput(ToolInput):
    cluster_id: Identifier


class ClusterMoneyInput(PageInput):
    cluster_id: Identifier | None = None
    app_ids: list[Identifier] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def scope(self):
        if bool(self.cluster_id) == bool(self.app_ids) or len(set(self.app_ids)) != len(self.app_ids):
            raise ValueError("Supply cluster_id or distinct app_ids, exclusively")
        return self


class ApplicationsInput(ToolInput):
    app_ids: list[Identifier] = Field(min_length=1, max_length=50)


class ToolError(BaseModel):
    code: str
    message: str


class ToolResponse(BaseModel):
    ok: bool
    tool: str
    data: dict[str, JsonValue] | None = None
    error: ToolError | None = None


INPUTS = {
    "cluster_money_flow": ClusterMoneyInput,
    "get_application": ApplicationInput,
    "neighbors": NeighborsInput,
    "money_flow": MoneyFlowInput,
    "get_evidence": EvidenceInput,
    "get_cluster": ClusterInput,
    "account_senders": NodeInput,
    "reports_mentioning": NodeInput,
    "timeline": ApplicationsInput,
    "tech_profile": ApplicationsInput,
    "entity_info": NodeInput,
}
DESCRIPTIONS = {
    "cluster_money_flow": "Read all-scope money aggregates, per-application summaries, shared recipients and source records. Supply cluster_id OR app_ids. Details paginate with limit/offset; counts cover all scope transfers.",
    "get_application": "Read a loan application and technical signals with personal identifiers masked.",
    "neighbors": "Read one-hop relations by node ID. Follow returned node IDs and paginate when truncated.",
    "money_flow": "Read outgoing transfers for an application, with evidence IDs and totals across all pages.",
    "get_evidence": "Read the masked source record behind an edge ID. Free text and names are omitted.",
    "get_cluster": "Read a stored cluster summary, application IDs and AI triage decision.",
    "account_senders": "Read applications that sent money to an account node. Paginate when truncated.",
    "reports_mentioning": "Read indexed report assessments mentioning an account, phone or domain node.",
    "timeline": "Read application and disbursement times, status and delinquency for up to 50 applications.",
    "tech_profile": "Aggregate technical and financial signals; missing data is noted.",
    "entity_info": "Read audited AI identity decisions and associated application IDs for a person or application node.",
}
