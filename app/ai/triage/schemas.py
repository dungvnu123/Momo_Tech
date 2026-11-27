from pydantic import Field, model_validator
from typing import Literal

from ..common.schemas import Confidence, Contract, Identifier, Reason

class ClusterSummary(Contract):
    cluster_id: Identifier
    app_ids: list[Identifier] = Field(min_length=1, max_length=100)
    size: int = Field(ge=1, le=100)
    applied_span_hours: float = Field(ge=0, allow_inf_nan=False)
    new_sim_ratio: Confidence
    vpn_ratio: Confidence
    emulator_ratio: Confidence
    suspicious_ekyc_ratio: Confidence | None
    median_fill_time_sec: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    rapid_outflow_ratio: Confidence
    stranger_outflow_ratio: Confidence
    shared_device_count: int = Field(ge=0)
    max_device_applications: int = Field(default=0, ge=0)
    max_reference_applications: int = Field(default=0, ge=0)
    same_person_multiple_identity_count: int = Field(default=0, ge=0)
    shared_recipient_count: int = Field(ge=0)
    reported_recipient_count: int = Field(ge=0)
    self_report_count: int = Field(ge=0)
    median_dpd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def size_matches(self):
        if len(set(self.app_ids)) != self.size or len(self.app_ids) != self.size:
            raise ValueError("size must match unique app_ids")
        return self

class TriageBatch(Contract):
    clusters: list[ClusterSummary] = Field(min_length=1, max_length=30)

class TriageDecision(Contract):
    cluster_id: Identifier
    decision: Literal["skip", "investigate"]
    suspected_type: str | None = Field(default=None, max_length=80)
    reason: Reason

class TriageDecisions(Contract):
    decisions: list[TriageDecision] = Field(min_length=1, max_length=30)
