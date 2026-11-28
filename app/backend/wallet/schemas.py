from pydantic import BaseModel, Field

MAX_LOAN = 20_000_000


class LoginIn(BaseModel):
    phone: str = Field(pattern="^0\\d{9}$")
    pin: str = Field(pattern="^\\d{6}$")


class LoanIn(BaseModel):
    amount: int = Field(ge=1000000, le=MAX_LOAN)


class TransferIn(BaseModel):
    to_type: str = Field(pattern="^(bank|momo_wallet)$")
    to_id: str = Field(min_length=8, max_length=19)
    to_bank: str = Field(max_length=20)
    to_name: str = Field(min_length=2, max_length=60)
    amount: int = Field(ge=10000, le=50000000)
    note: str = Field(default="", max_length=120)
    save_contact: bool = False
    confirm: bool = False
    coached: bool = False
