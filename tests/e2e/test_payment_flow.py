import asyncio
from uuid import UUID, uuid4

import httpx

from tests.integration.helpers import (
    BASE_URL,
    RECEIVER_URL,
    create_funded_customer,
    create_merchant,
    fetch_value,
    reset_state,
    wait_for,
)


def test_complete_payment_flow_publishes_event_and_webhook() -> None:
    reset_state()
    capture_correlation_id = str(uuid4())
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
        with httpx.Client(base_url=RECEIVER_URL, timeout=10) as receiver:
            receiver.post(
                "/accepted-secrets", json={"secret": endpoint.json()["signing_secret"]}
            ).raise_for_status()
        customer = create_funded_customer(client, headers)

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

        authorized = client.post(f"/api/v1/payments/{payment_id}/authorize", headers=headers)
        authorized.raise_for_status()
        assert authorized.json()["status"] == "AUTHORIZED"

        captured = client.post(
            f"/api/v1/payments/{payment_id}/capture",
            headers={**headers, "x-correlation-id": capture_correlation_id},
        )
        captured.raise_for_status()
        assert captured.json()["status"] == "CAPTURED"

    journal_count = asyncio.run(
        fetch_value(
            "select count(*) from journals where reference_type='payment_capture' and reference_id=$1",
            UUID(payment_id),
        )
    )
    assert journal_count == 1

    def outbox_published() -> bool:
        pending = asyncio.run(
            fetch_value(
                "select count(*) from outbox_events where aggregate_id=$1 and published_at is null",
                UUID(payment_id),
            )
        )
        return pending == 0

    wait_for(outbox_published)

    def webhook_succeeded() -> bool:
        count = asyncio.run(
            fetch_value(
                """
                select count(*)
                from webhook_deliveries wd
                join outbox_events oe on oe.event_id = wd.event_id
                where oe.aggregate_id=$1 and wd.status='SUCCEEDED'
                """,
                UUID(payment_id),
            )
        )
        return count == 1

    wait_for(webhook_succeeded, timeout_seconds=15)

    with httpx.Client(base_url=RECEIVER_URL, timeout=10) as receiver:
        received = receiver.get("/received")
        received.raise_for_status()
    deliveries = received.json()
    assert len(deliveries) == 1
    assert deliveries[0]["correlation_id"] == capture_correlation_id
