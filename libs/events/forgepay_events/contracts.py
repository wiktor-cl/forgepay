from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from forgepay_common.time import utc_now
from pydantic import BaseModel, Field


class EventType(StrEnum):
    PAYMENT_CREATED = "payment.created"
    PAYMENT_AUTHORIZED = "payment.authorized"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_CANCELLED = "payment.cancelled"
    PAYMENT_REFUNDED = "payment.refunded"
    RISK_APPROVED = "risk.approved"
    RISK_REJECTED = "risk.rejected"
    WEBHOOK_DELIVERY_FAILED = "webhook.delivery.failed"


class EventEnvelope(BaseModel, frozen=True):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    occurred_at: datetime = Field(default_factory=utc_now)
    correlation_id: UUID
    causation_id: UUID | None = None
    aggregate_id: UUID
    aggregate_type: str
    version: int = 1
    payload: dict[str, Any]
