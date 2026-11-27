from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..common.schemas import Confidence, Contract, Reason


class Indicator(Contract):
    kind: Literal["bank_account", "wallet", "phone", "url"]
    raw: str = Field(min_length=1, max_length=250)
    bank: str | None = Field(default=None, max_length=30)

class ReportRequest(Contract):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Report cannot be blank")
        return value

class ReportAnalysis(Contract):
    verdict: Literal["scam", "suspicious", "safe"]
    confidence: Confidence
    tactics: list[str] = Field(default_factory=list, max_length=10)
    indicators: list[Indicator] = Field(default_factory=list, max_length=30)
    reporter_is_victim: bool
    reasons: list[Reason] = Field(min_length=1, max_length=5)
    advice: Reason

    @model_validator(mode="after")
    def coherent_victim_verdict(self):
        if self.reporter_is_victim and self.verdict == "safe":
            raise ValueError("A report describing an actual scam victim cannot be labeled safe")
        return self
