import asyncio
from uuid import UUID, uuid4

import httpx

from tests.integration.helpers import (
    BASE_URL,
    create_funded_customer,
    create_merchant,
    fetch_value,
    reset_state,
)


async def _post(
    path: str, headers: dict[str, str], payload: dict[str, object] | None = None
) -> httpx.Response:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        return await client.post(path, headers=headers, json=payload)


def test_concurrent_identical_idempotent_requests_create_one_payment() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        customer = create_funded_customer(client, headers)
    idem = str(uuid4())
    payload = {"customer_id": customer["customer_id"], "amount_minor": 1000, "currency": "PLN"}

    async def run() -> list[httpx.Response]:
        return await asyncio.gather(
            *[
                _post("/api/v1/payments", {**headers, "Idempotency-Key": idem}, payload)
                for _ in range(50)
            ]
        )

    responses = asyncio.run(run())
    assert [response.status_code for response in responses].count(201) == 50
    assert len({response.json()["payment_id"] for response in responses}) == 1
    count = asyncio.run(fetch_value("select count(*) from payments"))
    assert count == 1


def test_concurrent_captures_for_same_authorization_allow_exactly_one_success() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        customer = create_funded_customer(client, headers)
        payment = client.post(
            "/api/v1/payments",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"customer_id": customer["customer_id"], "amount_minor": 1000, "currency": "PLN"},
        )
        payment.raise_for_status()
        payment_id = payment.json()["payment_id"]
        client.post(f"/api/v1/payments/{payment_id}/authorize", headers=headers).raise_for_status()

    async def run() -> list[httpx.Response]:
        return await asyncio.gather(
            *[_post(f"/api/v1/payments/{payment_id}/capture", headers) for _ in range(25)]
        )

    responses = asyncio.run(run())
    assert [response.status_code for response in responses].count(200) == 1
    journal_count = asyncio.run(
        fetch_value("select count(*) from journals where reference_type='payment_capture'")
    )
    assert journal_count == 1


def test_concurrent_overspending_preserves_ledger_balance() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        customer = create_funded_customer(client, headers)
        payment_ids: list[str] = []
        for _ in range(50):
            payment = client.post(
                "/api/v1/payments",
                headers={**headers, "Idempotency-Key": str(uuid4())},
                json={
                    "customer_id": customer["customer_id"],
                    "amount_minor": 1000,
                    "currency": "PLN",
                },
            )
            payment.raise_for_status()
            payment_id = payment.json()["payment_id"]
            payment_ids.append(payment_id)
            client.post(
                f"/api/v1/payments/{payment_id}/authorize", headers=headers
            ).raise_for_status()

    async def run() -> list[httpx.Response]:
        return await asyncio.gather(
            *[
                _post(f"/api/v1/payments/{payment_id}/capture", headers)
                for payment_id in payment_ids
            ]
        )

    responses = asyncio.run(run())
    assert [response.status_code for response in responses].count(200) == 10
    captured_total = asyncio.run(
        fetch_value(
            "select coalesce(sum(captured_amount_minor),0) from payments where status='CAPTURED'"
        )
    )
    assert captured_total == 10_000
    projected_cash = asyncio.run(
        fetch_value(
            """
            select coalesce(sum(case when je.direction='DEBIT' then je.amount_minor else -je.amount_minor end),0)
            from ledger_accounts la
            join journal_entries je on je.ledger_account_id=la.id
            where la.owner_id=$1 and la.name='customer_cash'
            """,
            UUID(customer["customer_id"]),
        )
    )
    assert projected_cash == 0
