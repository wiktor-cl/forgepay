import asyncio
import json
import subprocess
from uuid import UUID, uuid4

import httpx
from aiokafka import AIOKafkaProducer

from tests.integration.helpers import (
    BASE_URL,
    create_funded_customer,
    create_merchant,
    fetch_row,
    fetch_value,
    reset_state,
    wait_for,
)


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], check=True)


def _create_payment(headers: dict[str, str], customer_id: str) -> str:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        payment = client.post(
            "/api/v1/payments",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"customer_id": customer_id, "amount_minor": 1000, "currency": "PLN"},
        )
        payment.raise_for_status()
        return str(payment.json()["payment_id"])


def test_kafka_outage_leaves_outbox_pending_then_recovers() -> None:
    reset_state()
    compose("stop", "kafka")
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            _, headers = create_merchant(client)
            customer = create_funded_customer(client, headers)
            payment_id = _create_payment(headers, customer["customer_id"])
        pending = asyncio.run(
            fetch_value(
                "select count(*) from outbox_events where aggregate_id=$1 and published_at is null",
                UUID(payment_id),
            )
        )
        assert pending == 1
    finally:
        compose("start", "kafka")

    def outbox_recovered() -> bool:
        pending = asyncio.run(
            fetch_value(
                "select count(*) from outbox_events where aggregate_id=$1 and published_at is null",
                UUID(payment_id),
            )
        )
        return pending == 0

    wait_for(outbox_recovered, timeout_seconds=30)


async def _publish_duplicate_events(event: dict[str, object], times: int) -> None:
    producer = AIOKafkaProducer(bootstrap_servers="localhost:29092")
    await producer.start()
    try:
        for _ in range(times):
            await producer.send_and_wait(
                "forgepay.events",
                json.dumps(event).encode("utf-8"),
                key=str(event["event_id"]).encode("utf-8"),
            )
    finally:
        await producer.stop()


def test_duplicate_kafka_event_creates_one_webhook_side_effect() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        endpoint = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={
                "url": "http://webhook-receiver-demo:8010/webhooks/forgepay",
                "event_types": ["payment.captured"],
            },
        )
        endpoint.raise_for_status()
        customer = create_funded_customer(client, headers)
        payment_id = _create_payment(headers, customer["customer_id"])

    event_id = uuid4()
    event = {
        "event_id": str(event_id),
        "event_type": "payment.captured",
        "occurred_at": "2026-08-16T00:00:00Z",
        "correlation_id": str(uuid4()),
        "causation_id": None,
        "aggregate_id": payment_id,
        "aggregate_type": "payment",
        "version": 1,
        "payload": {"payment_id": payment_id},
    }
    asyncio.run(_publish_duplicate_events(event, 3))

    def side_effect_created_once() -> bool:
        row = asyncio.run(
            fetch_row(
                """
                select
                  (select count(*) from processed_events where event_id=$1) as processed,
                  (select count(*) from webhook_deliveries where event_id=$1) as deliveries
                """,
                event_id,
            )
        )
        return row is not None and row["processed"] == 1 and row["deliveries"] == 1

    wait_for(side_effect_created_once, timeout_seconds=20)


def test_webhook_retry_dead_letter_and_manual_replay() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        endpoint = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={
                "url": "http://webhook-receiver-demo:8010/webhooks/always-fail",
                "event_types": ["payment.captured"],
            },
        )
        endpoint.raise_for_status()
        customer = create_funded_customer(client, headers)
        payment_id = _create_payment(headers, customer["customer_id"])

    event = {
        "event_id": str(uuid4()),
        "event_type": "payment.captured",
        "occurred_at": "2026-08-16T00:00:00Z",
        "correlation_id": str(uuid4()),
        "causation_id": None,
        "aggregate_id": payment_id,
        "aggregate_type": "payment",
        "version": 1,
        "payload": {"payment_id": payment_id},
    }
    asyncio.run(_publish_duplicate_events(event, 1))

    def delivery_dead_lettered() -> UUID | None:
        row = asyncio.run(
            fetch_row(
                "select id, status, attempts from webhook_deliveries where event_id=$1",
                UUID(str(event["event_id"])),
            )
        )
        if row is not None and row["status"] == "DEAD_LETTER" and row["attempts"] == 3:
            return row["id"]
        return None

    delivery_id = wait_for(delivery_dead_lettered, timeout_seconds=30)
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        replay = client.post(f"/api/v1/webhooks/deliveries/{delivery_id}/replay", headers=headers)
        replay.raise_for_status()
        assert replay.json()["status"] == "PENDING"
