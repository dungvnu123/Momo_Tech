from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

AppID = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    app_id: AppID
    cluster_id: AppID | None = None
    conversation_id: str | None = None
    stream_response: bool = Field(default=False, alias="streamResponse")


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: Text
    source: str = Field(min_length=1, max_length=128, description="tool_call_id from a successful tool result in this run; not an edge ID")
    record_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=256)]] = Field(default_factory=list, max_length=20,
        description="Exact record_id values returned by that source tool, especially for application-level claims")


class ClusterAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["suspicious", "no_pattern_observed", "insufficient_data"]
    reason: Text
    evidence: list[Evidence] = Field(min_length=1, max_length=10)
    limitations: list[Text] = Field(default_factory=list, max_length=10)
    verification_status: Literal["unverified"] = "unverified"


class ApplicationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: AppID
    role: Literal["suspected_participant", "possible_victim", "no_adverse_evidence", "undetermined"]
    reason: Text
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)
    missing_information: list[Text] = Field(default_factory=list, max_length=10)
    assessment_status: Literal["assessed", "not_assessed"] = "assessed"
    verification_status: Literal["unverified"] = "unverified"

    @model_validator(mode="after")
    def grounded_role(self):
        if self.assessment_status == "assessed" and not self.evidence:
            raise ValueError("An assessed application needs application-specific evidence")
        if self.assessment_status == "not_assessed" and self.role != "undetermined":
            raise ValueError("An unassessed application must remain undetermined")
        if self.role == "undetermined" and not self.missing_information:
            raise ValueError("Explain which application information is missing")
        return self


class TransactionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transfer_id: AppID
    recommendation: Literal["allow", "warn", "hold", "review"] = Field(
        description="Recommendation for human review only. Hold needs a recorded SIMO/recipient warning; it does not identify the borrower as an offender.")
    reason: Text
    evidence: list[Evidence] = Field(min_length=1, max_length=10)


class CaseSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["fraud_ring", "victims", "benign", "inconclusive"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False,
                             description="Model's uncalibrated confidence in this verdict, not probability the borrower is a criminal. No fixed default for inconclusive.")
    summary: Text | None = None
    cluster_assessment: ClusterAssessment | None = None
    application_assessments: list[ApplicationAssessment] = Field(default_factory=list, max_length=100)
    missing_information: list[Text] = Field(default_factory=list, max_length=10)
    transaction_assessments: list[TransactionAssessment] = Field(default_factory=list, max_length=50)
    members: list[AppID] = Field(default_factory=list, max_length=100,
                                description="Nonempty application IDs for suspected offenders when verdict=fraud_ring. Empty for all other verdicts. No app: prefix.")
    victims: list[AppID] = Field(default_factory=list, max_length=100,
                                description="Application IDs of victims. Required nonempty when verdict=victims; must not overlap members. No app: prefix.")
    evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    benign_explanation: Text = Field(description="Legitimate alternative considered, and why supported or outweighed by the evidence. Does not itself determine the verdict.")
    actions: list[Text] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_case(self):
        if set(self.members) & set(self.victims):
            raise ValueError("Members and victims must be disjoint")
        if self.verdict == "fraud_ring" and not self.members:
            raise ValueError("Fraud verdict requires members")
        if self.verdict == "victims" and not self.victims:
            raise ValueError("Victim verdict requires victims")
        if self.verdict != "fraud_ring" and self.members:
            raise ValueError("Only fraud verdict may identify offenders")
        if self.verdict not in {"fraud_ring", "victims"} and self.victims:
            raise ValueError("Only a fraud or victim verdict may identify victims")
        if self.verdict != "inconclusive" and not self.evidence:
            raise ValueError("A definitive verdict requires evidence")
        return self


class ToolStep(BaseModel):
    tool_call_id: str
    name: str
    result: dict


class InvestigationResult(BaseModel):
    run_id: str
    app_id: str
    conversation_id: str | None = None
    status: Literal["completed", "limit_reached", "failed"]
    reason: str | None = None
    case: CaseSubmission
    steps: list[ToolStep]
    model_turns: int = Field(default=0, ge=0)


def submit_definition() -> dict:
    return {"name": "submit_case", "description": "Finish the investigation. Cite successful tool call IDs; call alone.",
            "parameters": CaseSubmission.model_json_schema()}
