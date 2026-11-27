from datetime import date
from pydantic import field_validator
from pydantic import Field, model_validator
from typing import Literal

from ..common.schemas import Confidence, Contract, Identifier, Reason

class EntityRecord(Contract):
    app_id: Identifier
    full_name: str = Field(min_length=1, max_length=150)
    dob: str = Field(min_length=1, max_length=20)
    address: str = Field(min_length=1, max_length=300)
    device_token: str | None = None

    @field_validator("dob")
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value

class EntityPair(Contract):
    pair_id: Identifier
    left: EntityRecord
    right: EntityRecord

    @model_validator(mode="after")
    def distinct(self):
        if self.left.app_id == self.right.app_id:
            raise ValueError("Entity pair must contain two distinct applications")
        return self

class EntityBatch(Contract):
    pairs: list[EntityPair] = Field(min_length=1, max_length=20)

class EntityDecision(Contract):
    pair_id: Identifier
    decision: Literal["same", "different", "same_household"]
    confidence: Confidence
    reason: Reason

class EntityDecisions(Contract):
    decisions: list[EntityDecision] = Field(min_length=1, max_length=20)
