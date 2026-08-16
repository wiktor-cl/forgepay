from typing import Any
from uuid import UUID

from forgepay_common.money import Currency
from pydantic import BaseModel, EmailStr, Field, HttpUrl


class ErrorEnvelope(BaseModel):
    error: dict[str, str]


class MerchantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    risk_level: int = Field(default=1, ge=1, le=5)


class MerchantCreated(BaseModel):
    merchant_id: UUID
    api_key: str


class CustomerCreate(BaseModel):
    email: EmailStr
    currency: Currency


class CustomerCreated(BaseModel):
    customer_id: UUID
    account_id: UUID


class FundAccountRequest(BaseModel):
    amount_minor: int = Field(gt=0)
    currency: Currency


class PaymentCreate(BaseModel):
    customer_id: UUID
    amount_minor: int = Field(gt=0)
    currency: Currency


class PaymentResponse(BaseModel):
    payment_id: UUID
    status: str
    amount_minor: int
    currency: str
    captured_amount_minor: int
    refunded_amount_minor: int


class RefundRequest(BaseModel):
    amount_minor: int = Field(gt=0)


class WebhookEndpointCreate(BaseModel):
    url: HttpUrl
    event_types: list[str]


class WebhookEndpointCreated(BaseModel):
    endpoint_id: UUID
    signing_secret: str


class JournalResponse(BaseModel):
    journal_id: UUID
    reference_id: UUID
    entries: list[dict[str, Any]]
