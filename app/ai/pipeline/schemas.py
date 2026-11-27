from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.common.schemas import Identifier


class PipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_limit: int = Field(default=8, ge=1, le=12)
    entity_pair_limit: int = Field(default=10, ge=0, le=20)
    cluster_limit: int = Field(default=4, ge=1, le=6)
    investigation_limit: int = Field(default=2, ge=0, le=4)
    cluster_ids: list[Identifier] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_selection(self):
        if len(set(self.cluster_ids)) != len(self.cluster_ids) or len(self.cluster_ids) > self.cluster_limit:
            raise ValueError("Explicit cluster IDs must be unique and fit cluster_limit")
        return self
