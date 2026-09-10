"""Pydantic schemas for Payment (Transbank Webpay Plus) API."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class PaymentLinkCreate(BaseModel):
    """Request body to generate a payment link for a deal reservation."""

    amount: int  # CLP, no decimals

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        if v > 999_999_999:
            raise ValueError("amount exceeds the maximum allowed")
        return v


class PaymentLinkResponse(BaseModel):
    """Response after creating a payment link."""

    payment_id: int
    deal_id: int
    buy_order: str
    amount: int
    status: str
    pay_url: str  # public short URL to share with the buyer
    environment: str


class PaymentRead(BaseModel):
    id: int
    deal_id: int
    broker_id: int
    amount: int
    status: str
    provider: str
    environment: str
    buy_order: str
    authorization_code: Optional[str] = None
    card_last4: Optional[str] = None
    payment_type_code: Optional[str] = None
    installments_number: Optional[int] = None
    transaction_date: Optional[str] = None
    committed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Public link to (re)share while the payment is still payable (created/pending).
    pay_url: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Broker Transbank config schemas ──────────────────────────────────────────

class PaymentConfigRead(BaseModel):
    """Broker payment config — never exposes the API key in clear text."""

    provider: str = "transbank"
    environment: str = "integration"
    enabled: bool = False
    commerce_code_masked: Optional[str] = None
    has_api_key: bool = False


class PaymentConfigUpdate(BaseModel):
    commerce_code: Optional[str] = None
    api_key: Optional[str] = None  # write-only; encrypted at rest
    environment: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("integration", "production"):
            raise ValueError("environment must be 'integration' or 'production'")
        return v
