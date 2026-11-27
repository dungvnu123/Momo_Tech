from typing import Literal

from pydantic import Field

from ..common.schemas import Confidence, Contract, Reason


class TransferCheck(Contract):
    loan_amount: int = Field(gt=0)
    transfer_amount: int = Field(gt=0)
    minutes_after_disbursal: float = Field(ge=0, allow_inf_nan=False)
    prior_outflow_since_disbursal: int = Field(default=0, ge=0)
    recipient_name_matches: bool | None = None
    recipient_in_contacts: bool | None = None
    contact_saved_minutes_ago: int | None = Field(default=None, ge=0)
    prior_transfers_to_recipient: int = Field(default=0, ge=0)
    simo_flag: bool = False
    reported_recipient_count: int = Field(default=0, ge=0)
    recipient_is_merchant: bool = False

class TransferDecision(Contract):
    decision: Literal["allow", "warn", "hold"]
    confidence: Confidence
    reasons: list[Reason] = Field(min_length=1, max_length=5)
    advice: Reason
