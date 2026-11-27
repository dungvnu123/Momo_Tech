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
    # Tín hiệu backend bổ sung (app khách) — đều tuỳ chọn, thiếu thì coi như không có
    recipient_ring_senders: int = Field(default=0, ge=0)   # số hồ sơ vay trong 1 vụ đường dây ĐÃ điều tra từng chuyển cho người nhận này
    share_of_balance: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)   # số tiền / số dư ví (không gửi số dư tuyệt đối)
    note_tags: list[Literal["fee", "debt_collection", "urgent"]] = Field(default_factory=list, max_length=3)   # nhãn từ nội dung CK (không gửi chữ gốc)
    customer_says_coached: bool = False   # khách trả lời "có người đang hướng dẫn tôi chuyển"

class TransferDecision(Contract):
    decision: Literal["allow", "warn", "hold"]
    confidence: Confidence
    reasons: list[Reason] = Field(min_length=1, max_length=5)
    advice: Reason
