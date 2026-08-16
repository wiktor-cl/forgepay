import asyncio
import time
from collections.abc import Callable
from typing import Any

import asyncpg
import httpx

BASE_URL = "http://localhost:8000"
RECEIVER_URL = "http://localhost:8010"
DATABASE_URL = "postgresql://forgepay:forgepay@localhost:5432/forgepay"


async def reset_database() -> None:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        await connection.execute(
            """
            truncate table
              audit_logs,
              webhook_deliveries,
              webhook_secrets,
              webhook_endpoints,
              processed_events,
              outbox_events,
              idempotency_records,
              journal_entries,
              journals,
              ledger_accounts,
              refunds,
              payments,
              accounts,
              customers,
              api_keys,
              merchants
            cascade
            """
        )
    finally:
        await connection.close()


def reset_state() -> None:
    asyncio.run(reset_database())
    with httpx.Client(timeout=5) as client:
        client.post(f"{RECEIVER_URL}/reset").raise_for_status()


def wait_for(predicate: Callable[[], Any], timeout_seconds: float = 10) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last: Any = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(0.2)
    raise AssertionError(f"condition did not become true; last={last!r}")


def create_merchant(client: httpx.Client) -> tuple[str, dict[str, str]]:
    merchant = client.post("/api/v1/merchants", json={"name": "Integration Merchant"})
    merchant.raise_for_status()
    body = merchant.json()
    return str(body["api_key"]), {"Authorization": f"Bearer {body['api_key']}"}


def create_funded_customer(client: httpx.Client, headers: dict[str, str]) -> dict[str, str]:
    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"email": f"buyer-{time.time_ns()}@example.com", "currency": "PLN"},
    )
    customer.raise_for_status()
    body = customer.json()
    funding = client.post(
        f"/api/v1/accounts/{body['account_id']}/fund",
        headers=headers,
        json={"amount_minor": 10_000, "currency": "PLN"},
    )
    funding.raise_for_status()
    return body


async def fetch_value(query: str, *args: object) -> Any:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        return await connection.fetchval(query, *args)
    finally:
        await connection.close()


async def fetch_row(query: str, *args: object) -> asyncpg.Record | None:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        return await connection.fetchrow(query, *args)
    finally:
        await connection.close()


async def fetch_all(query: str, *args: object) -> list[asyncpg.Record]:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        return list(await connection.fetch(query, *args))
    finally:
        await connection.close()
