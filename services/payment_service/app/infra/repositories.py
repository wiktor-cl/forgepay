from typing import Any
from uuid import UUID

from app.domain.idempotency import IdempotencyConflictError
from app.infra.models import (
    AuditLog,
    IdempotencyRecord,
    Journal,
    JournalEntry,
    LedgerAccount,
    OutboxEvent,
    Payment,
    ProcessedEvent,
)
from forgepay_common.money import LedgerLine
from forgepay_common.time import utc_now
from forgepay_events import EventEnvelope, EventType
from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


async def claim_idempotency(
    session: AsyncSession,
    merchant_id: UUID,
    key: str,
    fingerprint: str,
) -> IdempotencyRecord:
    stmt = (
        pg_insert(IdempotencyRecord)
        .values(key=key, merchant_id=merchant_id, request_fingerprint=fingerprint)
        .on_conflict_do_nothing(index_elements=["key", "merchant_id"])
        .returning(IdempotencyRecord)
    )
    claimed = (await session.execute(stmt)).scalar_one_or_none()
    if claimed is not None:
        return claimed

    existing = await session.get(
        IdempotencyRecord, {"key": key, "merchant_id": merchant_id}, with_for_update=True
    )
    if existing is None:
        raise RuntimeError("idempotency insert raced without observable row")
    if existing.request_fingerprint != fingerprint:
        raise IdempotencyConflictError("same idempotency key used with a different payload")
    return existing


async def complete_idempotency(
    session: AsyncSession,
    record: IdempotencyRecord,
    status: int,
    body: dict[str, Any],
    resource_id: UUID,
) -> None:
    record.response_status = status
    record.response_body = body
    record.resource_id = resource_id


async def append_outbox(
    session: AsyncSession,
    event_type: EventType,
    aggregate_id: UUID,
    aggregate_type: str,
    payload: dict[str, Any],
    correlation_id: UUID,
) -> OutboxEvent:
    event = EventEnvelope(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        payload=payload,
        correlation_id=correlation_id,
    )
    row = OutboxEvent(
        event_id=event.event_id,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        event_type=event_type.value,
        payload=event.model_dump(mode="json"),
    )
    session.add(row)
    return row


async def append_audit(
    session: AsyncSession,
    actor: str,
    action: str,
    resource: str,
    correlation_id: UUID,
    metadata: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            resource=resource,
            correlation_id=correlation_id,
            metadata_json=metadata,
        )
    )


async def ensure_ledger_account(
    session: AsyncSession,
    owner_id: UUID,
    name: str,
    currency: str,
    normal_balance: str,
) -> LedgerAccount:
    existing = await session.scalar(
        select(LedgerAccount).where(
            LedgerAccount.owner_id == owner_id,
            LedgerAccount.name == name,
            LedgerAccount.currency == currency,
        )
    )
    if existing is not None:
        return existing
    stmt = (
        pg_insert(LedgerAccount)
        .values(owner_id=owner_id, name=name, currency=currency, normal_balance=normal_balance)
        .on_conflict_do_nothing(
            constraint="uq_ledger_account_owner_name_currency",
        )
        .returning(LedgerAccount)
    )
    inserted = (await session.execute(stmt)).scalar_one_or_none()
    if inserted is not None:
        return inserted
    found = await session.scalar(
        select(LedgerAccount).where(
            LedgerAccount.owner_id == owner_id,
            LedgerAccount.name == name,
            LedgerAccount.currency == currency,
        )
    )
    if found is None:
        raise RuntimeError("ledger account upsert failed")
    return found


async def create_journal(
    session: AsyncSession,
    reference_type: str,
    reference_id: UUID,
    currency: str,
    accounts_by_name: dict[str, LedgerAccount],
    lines: list[LedgerLine],
) -> Journal:
    journal = Journal(
        reference_type=reference_type,
        reference_id=reference_id,
        currency=currency,
        status="DRAFT",
        posted_at=None,
    )
    session.add(journal)
    await session.flush()
    for line in lines:
        account = accounts_by_name[line.account]
        session.add(
            JournalEntry(
                journal_id=journal.id,
                ledger_account_id=account.id,
                direction=line.direction,
                amount_minor=line.money.amount_minor,
                currency=line.money.currency.value,
            )
        )
    await session.flush()
    journal.status = "POSTED"
    journal.posted_at = utc_now()
    return journal


async def mark_event_processed(session: AsyncSession, event_id: UUID, consumer_name: str) -> bool:
    stmt = (
        pg_insert(ProcessedEvent)
        .values(event_id=event_id, consumer_name=consumer_name)
        .on_conflict_do_nothing(index_elements=["event_id", "consumer_name"])
        .returning(ProcessedEvent.event_id)
    )
    inserted = (await session.execute(stmt)).scalar_one_or_none()
    return inserted is not None


def payment_for_update(payment_id: UUID, merchant_id: UUID) -> Select[tuple[Payment]]:
    return (
        select(Payment)
        .where(Payment.id == payment_id, Payment.merchant_id == merchant_id)
        .with_for_update()
    )


async def pending_outbox(session: AsyncSession, limit: int = 100) -> list[OutboxEvent]:
    result = await session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(result)


async def mark_published(session: AsyncSession, event: OutboxEvent) -> None:
    event.published_at = utc_now()


async def bump_publish_retry(session: AsyncSession, event: OutboxEvent) -> None:
    event.retry_count += 1
    await session.flush()
