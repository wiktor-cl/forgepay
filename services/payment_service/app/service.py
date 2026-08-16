from typing import Any
from uuid import UUID

from forgepay_common.money import Currency, Money
from forgepay_common.time import utc_now
from forgepay_events import EventType
from forgepay_observability.metrics import payments_created_total, payments_failed_total
from forgepay_security.api_keys import generate_api_key, hash_secret
from forgepay_security.fingerprints import canonical_fingerprint
from forgepay_security.webhooks import sign_webhook
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CustomerCreate,
    FundAccountRequest,
    MerchantCreate,
    PaymentCreate,
    RefundRequest,
    WebhookEndpointCreate,
)
from app.domain.idempotency import IdempotencyConflictError
from app.domain.ledger import capture as capture_lines
from app.domain.ledger import refund as refund_lines
from app.domain.ledger import simulated_funding
from app.domain.payment import PaymentStatus, transition
from app.domain.risk import RiskDecision, evaluate_risk
from app.infra.models import (
    Account,
    ApiKey,
    Customer,
    JournalEntry,
    LedgerAccount,
    Merchant,
    Payment,
    Refund,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.infra.repositories import (
    append_audit,
    append_outbox,
    claim_idempotency,
    complete_idempotency,
    create_journal,
    ensure_ledger_account,
    mark_event_processed,
    payment_for_update,
)
from app.settings import Settings


class BusinessError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def payment_response(payment: Payment) -> dict[str, Any]:
    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "captured_amount_minor": payment.captured_amount_minor,
        "refunded_amount_minor": payment.refunded_amount_minor,
    }


async def create_merchant(
    session: AsyncSession, request: MerchantCreate, correlation_id: UUID
) -> dict[str, Any]:
    raw_key, digest = generate_api_key(live=False)
    merchant = Merchant(name=request.name, risk_level=request.risk_level)
    session.add(merchant)
    await session.flush()
    session.add(
        ApiKey(
            merchant_id=merchant.id,
            key_hash=digest,
            scopes=["payments:read", "payments:write", "refunds:write", "webhooks:manage"],
        )
    )
    await append_audit(
        session,
        actor=f"merchant:{merchant.id}",
        action="api_key.created",
        resource=f"merchant:{merchant.id}",
        correlation_id=correlation_id,
        metadata={
            "scopes": ["payments:read", "payments:write", "refunds:write", "webhooks:manage"]
        },
    )
    return {"merchant_id": str(merchant.id), "api_key": raw_key}


async def create_customer(
    session: AsyncSession, merchant_id: UUID, request: CustomerCreate, correlation_id: UUID
) -> dict[str, Any]:
    customer = Customer(merchant_id=merchant_id, email=str(request.email))
    session.add(customer)
    await session.flush()
    account = Account(customer_id=customer.id, currency=request.currency.value)
    session.add(account)
    await session.flush()
    await append_audit(
        session,
        actor=f"merchant:{merchant_id}",
        action="customer.created",
        resource=f"customer:{customer.id}",
        correlation_id=correlation_id,
        metadata={"account_currency": request.currency.value},
    )
    return {"customer_id": str(customer.id), "account_id": str(account.id)}


async def fund_account(
    session: AsyncSession,
    merchant_id: UUID,
    account_id: UUID,
    request: FundAccountRequest,
    correlation_id: UUID,
) -> dict[str, Any]:
    account = await session.get(Account, account_id, with_for_update=True)
    if account is None:
        raise BusinessError("ACCOUNT_NOT_FOUND", "Account was not found.")
    customer = await session.get(Customer, account.customer_id)
    if customer is None or customer.merchant_id != merchant_id:
        raise BusinessError("ACCOUNT_NOT_FOUND", "Account was not found.")
    if account.currency != request.currency.value:
        raise BusinessError(
            "CURRENCY_MISMATCH", "Funding currency must match the account currency."
        )
    customer_cash = await ensure_ledger_account(
        session, account.customer_id, "customer_cash", account.currency, "DEBIT"
    )
    funding_source = await ensure_ledger_account(
        session, merchant_id, "simulated_provider_funding", account.currency, "CREDIT"
    )
    amount = Money(amount_minor=request.amount_minor, currency=request.currency)
    journal = await create_journal(
        session,
        "account_funding",
        account.id,
        account.currency,
        {"customer_cash": customer_cash, "simulated_provider_funding": funding_source},
        [
            *simulated_funding(amount, "customer_cash", "simulated_provider_funding"),
        ],
    )
    await append_audit(
        session,
        actor=f"merchant:{merchant_id}",
        action="account.funded",
        resource=f"account:{account.id}",
        correlation_id=correlation_id,
        metadata={"amount_minor": request.amount_minor, "currency": request.currency.value},
    )
    return {"journal_id": str(journal.id)}


async def available_balance(session: AsyncSession, owner_id: UUID, currency: str) -> int:
    accounts = await session.scalars(
        select(LedgerAccount).where(
            LedgerAccount.owner_id == owner_id, LedgerAccount.currency == currency
        )
    )
    account_ids = [account.id for account in accounts if account.name == "customer_cash"]
    if not account_ids:
        return 0
    debit_sum = await session.scalar(
        select(func.coalesce(func.sum(JournalEntry.amount_minor), 0)).where(
            JournalEntry.ledger_account_id.in_(account_ids),
            JournalEntry.direction == "DEBIT",
        )
    )
    credit_sum = await session.scalar(
        select(func.coalesce(func.sum(JournalEntry.amount_minor), 0)).where(
            JournalEntry.ledger_account_id.in_(account_ids),
            JournalEntry.direction == "CREDIT",
        )
    )
    return int(debit_sum or 0) - int(credit_sum or 0)


async def create_payment(
    session: AsyncSession,
    merchant_id: UUID,
    request: PaymentCreate,
    idempotency_key: str,
    correlation_id: UUID,
) -> tuple[int, dict[str, Any]]:
    fingerprint = canonical_fingerprint(request.model_dump(mode="json"))
    try:
        idempotency = await claim_idempotency(session, merchant_id, idempotency_key, fingerprint)
    except IdempotencyConflictError as exc:
        raise BusinessError("IDEMPOTENCY_CONFLICT", str(exc)) from exc
    if idempotency.response_body is not None and idempotency.response_status is not None:
        return idempotency.response_status, idempotency.response_body

    customer = await session.get(Customer, request.customer_id)
    if customer is None or customer.merchant_id != merchant_id:
        raise BusinessError("CUSTOMER_NOT_FOUND", "Customer was not found for this merchant.")
    merchant = await session.get(Merchant, merchant_id)
    if merchant is None:
        raise BusinessError("MERCHANT_NOT_FOUND", "Merchant was not found.")
    risk = evaluate_risk(request.amount_minor, request.currency.value, merchant.risk_level)
    status = PaymentStatus.PENDING if risk.decision != RiskDecision.REJECT else PaymentStatus.FAILED
    payment = Payment(
        merchant_id=merchant_id,
        customer_id=request.customer_id,
        amount_minor=request.amount_minor,
        currency=request.currency.value,
        status=status.value,
    )
    session.add(payment)
    await session.flush()
    event_type = (
        EventType.PAYMENT_CREATED if status != PaymentStatus.FAILED else EventType.PAYMENT_FAILED
    )
    await append_outbox(
        session,
        event_type,
        payment.id,
        "payment",
        {"payment_id": str(payment.id), "status": payment.status, "risk": risk.model_dump()},
        correlation_id,
    )
    await append_audit(
        session,
        actor=f"merchant:{merchant_id}",
        action="payment.created",
        resource=f"payment:{payment.id}",
        correlation_id=correlation_id,
        metadata={"risk": risk.model_dump()},
    )
    body = payment_response(payment)
    await complete_idempotency(session, idempotency, 201, body, payment.id)
    payments_created_total.inc()
    if status == PaymentStatus.FAILED:
        payments_failed_total.inc()
    return 201, body


async def authorize_payment(
    session: AsyncSession, merchant_id: UUID, payment_id: UUID, correlation_id: UUID
) -> dict[str, Any]:
    payment = await session.scalar(payment_for_update(payment_id, merchant_id))
    if payment is None:
        raise BusinessError("PAYMENT_NOT_FOUND", "Payment was not found.")
    transition(PaymentStatus(payment.status), PaymentStatus.AUTHORIZED)
    customer = await session.get(Customer, payment.customer_id, with_for_update=True)
    if customer is None:
        raise BusinessError("CUSTOMER_NOT_FOUND", "Customer was not found.")
    balance = await available_balance(session, customer.id, payment.currency)
    if balance < payment.amount_minor:
        payment.status = PaymentStatus.FAILED.value
        await append_outbox(
            session,
            EventType.PAYMENT_FAILED,
            payment.id,
            "payment",
            {"payment_id": str(payment.id), "reason": "INSUFFICIENT_FUNDS"},
            correlation_id,
        )
        payments_failed_total.inc()
        raise BusinessError("INSUFFICIENT_FUNDS", "Available balance is insufficient.")
    payment.status = PaymentStatus.AUTHORIZED.value
    payment.updated_at = utc_now()
    await append_outbox(
        session,
        EventType.PAYMENT_AUTHORIZED,
        payment.id,
        "payment",
        {
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        },
        correlation_id,
    )
    await append_audit(
        session,
        actor=f"merchant:{merchant_id}",
        action="payment.authorized",
        resource=f"payment:{payment.id}",
        correlation_id=correlation_id,
        metadata={},
    )
    return payment_response(payment)


async def capture_payment(
    session: AsyncSession, merchant_id: UUID, payment_id: UUID, correlation_id: UUID
) -> dict[str, Any]:
    payment = await session.scalar(payment_for_update(payment_id, merchant_id))
    if payment is None:
        raise BusinessError("PAYMENT_NOT_FOUND", "Payment was not found.")
    transition(PaymentStatus(payment.status), PaymentStatus.CAPTURED)
    customer = await session.get(Customer, payment.customer_id, with_for_update=True)
    if customer is None:
        raise BusinessError("CUSTOMER_NOT_FOUND", "Customer was not found.")
    balance = await available_balance(session, customer.id, payment.currency)
    if balance < payment.amount_minor:
        raise BusinessError("INSUFFICIENT_FUNDS", "Available balance is insufficient.")
    customer_cash = await ensure_ledger_account(
        session, customer.id, "customer_cash", payment.currency, "DEBIT"
    )
    merchant_receivable = await ensure_ledger_account(
        session, merchant_id, "merchant_receivable", payment.currency, "CREDIT"
    )
    amount = Money(amount_minor=payment.amount_minor, currency=Currency(payment.currency))
    try:
        await create_journal(
            session,
            "payment_capture",
            payment.id,
            payment.currency,
            {"customer_cash": customer_cash, "merchant_receivable": merchant_receivable},
            capture_lines(amount, "customer_cash", "merchant_receivable"),
        )
    except IntegrityError as exc:
        raise BusinessError(
            "PAYMENT_ALREADY_CAPTURED", "Payment has already been captured."
        ) from exc
    payment.status = PaymentStatus.CAPTURED.value
    payment.captured_amount_minor = payment.amount_minor
    payment.updated_at = utc_now()
    await append_outbox(
        session,
        EventType.PAYMENT_CAPTURED,
        payment.id,
        "payment",
        {
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        },
        correlation_id,
    )
    await append_audit(
        session,
        actor=f"merchant:{merchant_id}",
        action="payment.captured",
        resource=f"payment:{payment.id}",
        correlation_id=correlation_id,
        metadata={},
    )
    return payment_response(payment)


async def cancel_payment(
    session: AsyncSession, merchant_id: UUID, payment_id: UUID, correlation_id: UUID
) -> dict[str, Any]:
    payment = await session.scalar(payment_for_update(payment_id, merchant_id))
    if payment is None:
        raise BusinessError("PAYMENT_NOT_FOUND", "Payment was not found.")
    transition(PaymentStatus(payment.status), PaymentStatus.CANCELLED)
    payment.status = PaymentStatus.CANCELLED.value
    payment.updated_at = utc_now()
    await append_outbox(
        session, EventType.PAYMENT_CANCELLED, payment.id, "payment", {}, correlation_id
    )
    return payment_response(payment)


async def refund_payment(
    session: AsyncSession,
    merchant_id: UUID,
    payment_id: UUID,
    request: RefundRequest,
    correlation_id: UUID,
) -> dict[str, Any]:
    payment = await session.scalar(payment_for_update(payment_id, merchant_id))
    if payment is None:
        raise BusinessError("PAYMENT_NOT_FOUND", "Payment was not found.")
    if PaymentStatus(payment.status) not in {
        PaymentStatus.CAPTURED,
        PaymentStatus.PARTIALLY_REFUNDED,
    }:
        raise BusinessError("PAYMENT_NOT_REFUNDABLE", "Only captured payments can be refunded.")
    remaining = payment.captured_amount_minor - payment.refunded_amount_minor
    if request.amount_minor > remaining:
        raise BusinessError("REFUND_EXCEEDS_CAPTURE", "Refund amount exceeds captured amount.")
    customer = await session.get(Customer, payment.customer_id)
    if customer is None:
        raise BusinessError("CUSTOMER_NOT_FOUND", "Customer was not found.")
    customer_cash = await ensure_ledger_account(
        session, customer.id, "customer_cash", payment.currency, "DEBIT"
    )
    merchant_receivable = await ensure_ledger_account(
        session, merchant_id, "merchant_receivable", payment.currency, "CREDIT"
    )
    refund = Refund(
        payment_id=payment.id,
        amount_minor=request.amount_minor,
        currency=payment.currency,
        status="SUCCEEDED",
    )
    session.add(refund)
    await session.flush()
    amount = Money(amount_minor=request.amount_minor, currency=Currency(payment.currency))
    await create_journal(
        session,
        "payment_refund",
        refund.id,
        payment.currency,
        {"customer_cash": customer_cash, "merchant_receivable": merchant_receivable},
        refund_lines(amount, "merchant_receivable", "customer_cash"),
    )
    payment.refunded_amount_minor += request.amount_minor
    payment.status = (
        PaymentStatus.REFUNDED.value
        if payment.refunded_amount_minor == payment.captured_amount_minor
        else PaymentStatus.PARTIALLY_REFUNDED.value
    )
    await append_outbox(
        session,
        EventType.PAYMENT_REFUNDED,
        payment.id,
        "payment",
        {
            "payment_id": str(payment.id),
            "refund_id": str(refund.id),
            "amount_minor": request.amount_minor,
        },
        correlation_id,
    )
    return payment_response(payment)


async def register_webhook(
    session: AsyncSession,
    merchant_id: UUID,
    request: WebhookEndpointCreate,
    correlation_id: UUID,
) -> dict[str, Any]:
    secret = Settings().webhook_secret
    endpoint = WebhookEndpoint(
        merchant_id=merchant_id,
        url=str(request.url),
        secret_hash=hash_secret(secret),
        event_types=request.event_types,
    )
    session.add(endpoint)
    await append_audit(
        session,
        actor=f"merchant:{merchant_id}",
        action="webhook.created",
        resource=f"webhook_endpoint:{endpoint.id}",
        correlation_id=correlation_id,
        metadata={"event_types": request.event_types},
    )
    return {"endpoint_id": str(endpoint.id), "signing_secret": secret}


async def process_payment_event_for_webhooks(
    session: AsyncSession, event_id: UUID, event_type: str, payload: dict[str, Any]
) -> bool:
    claimed = await mark_event_processed(session, event_id, "webhook-service")
    if not claimed:
        return False
    payment_id = UUID(str(payload["payload"]["payment_id"]))
    payment = await session.get(Payment, payment_id)
    if payment is None:
        return True
    endpoints = await session.scalars(
        select(WebhookEndpoint).where(
            WebhookEndpoint.merchant_id == payment.merchant_id,
            WebhookEndpoint.enabled.is_(True),
        )
    )
    for endpoint in endpoints:
        if event_type in endpoint.event_types:
            session.add(
                WebhookDelivery(endpoint_id=endpoint.id, event_id=event_id, status="PENDING")
            )
    return True


def sign_delivery_body(secret: str, timestamp: int, body: bytes) -> str:
    return sign_webhook(secret, timestamp, body)
