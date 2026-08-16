import asyncio
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest

from tests.integration.helpers import (
    BASE_URL,
    DATABASE_URL,
    create_merchant,
    fetch_row,
    fetch_value,
    reset_state,
)


def test_failed_authorization_persists_failed_state_and_outbox_event() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        customer = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"email": "unfunded@example.com", "currency": "PLN"},
        )
        customer.raise_for_status()
        payment = client.post(
            "/api/v1/payments",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={
                "customer_id": customer.json()["customer_id"],
                "amount_minor": 1000,
                "currency": "PLN",
            },
        )
        payment.raise_for_status()
        payment_id = payment.json()["payment_id"]

        authorization = client.post(f"/api/v1/payments/{payment_id}/authorize", headers=headers)
        assert authorization.status_code == 409
        assert authorization.json()["detail"]["error"]["code"] == "INSUFFICIENT_FUNDS"

    row = asyncio.run(
        fetch_row(
            """
            select
              p.status,
              count(oe.event_id) filter (where oe.event_type='payment.failed') as failed_events
            from payments p
            left join outbox_events oe on oe.aggregate_id=p.id
            where p.id=$1
            group by p.status
            """,
            UUID(payment_id),
        )
    )
    assert row is not None
    assert row["status"] == "FAILED"
    assert row["failed_events"] == 1


async def _execute_sql(query: str, *args: object) -> None:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        await connection.execute(query, *args)
    finally:
        await connection.close()


def test_database_rejects_unbalanced_posted_journal() -> None:
    reset_state()
    with pytest.raises(asyncpg.PostgresError, match="must have entries|unbalanced"):
        asyncio.run(
            _execute_sql(
                """
                insert into journals(id, reference_type, reference_id, currency, status, posted_at)
                values($1, 'manual_bad', $2, 'PLN', 'POSTED', now())
                """,
                uuid4(),
                uuid4(),
            )
        )


def test_database_prevents_mutating_posted_journal_entries() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        customer = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"email": "ledger@example.com", "currency": "PLN"},
        )
        customer.raise_for_status()
        funding = client.post(
            f"/api/v1/accounts/{customer.json()['account_id']}/fund",
            headers=headers,
            json={"amount_minor": 1000, "currency": "PLN"},
        )
        funding.raise_for_status()

    entry_id = asyncio.run(fetch_value("select id from journal_entries limit 1"))
    assert entry_id is not None
    with pytest.raises(asyncpg.PostgresError, match="immutable"):
        asyncio.run(
            _execute_sql(
                "update journal_entries set amount_minor=amount_minor+1 where id=$1",
                entry_id,
            )
        )
