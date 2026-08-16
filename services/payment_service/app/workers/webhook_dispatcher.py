import asyncio
import json
import random
import time
from datetime import timedelta

import httpx
from app.infra.database import SessionFactory
from app.infra.models import OutboxEvent, WebhookDelivery, WebhookEndpoint
from app.service import active_webhook_secret, sign_delivery_body
from app.settings import Settings
from forgepay_common.time import utc_now
from forgepay_observability.metrics import webhook_delivery_failures_total, webhook_delivery_total
from sqlalchemy import select


def next_delay(attempts: int) -> float:
    return float(min(300.0, (2**attempts) + random.uniform(0, 1)))


async def dispatch_once() -> int:
    settings = Settings()
    sent = 0
    async with SessionFactory() as session, session.begin():
        deliveries = await session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.status.in_(["PENDING", "RETRY"]))
            .where(
                (WebhookDelivery.next_attempt_at.is_(None))
                | (WebhookDelivery.next_attempt_at <= utc_now())
            )
            .limit(25)
            .with_for_update(skip_locked=True)
        )
        async with httpx.AsyncClient(timeout=5) as client:
            for delivery in deliveries:
                endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
                if endpoint is None:
                    delivery.status = "DEAD_LETTER"
                    continue
                event = await session.get(OutboxEvent, delivery.event_id)
                correlation_id = (
                    str(event.payload.get("correlation_id"))
                    if event is not None and isinstance(event.payload, dict)
                    else str(delivery.event_id)
                )
                body = json.dumps(
                    {"event_id": str(delivery.event_id)}, separators=(",", ":")
                ).encode()
                try:
                    secret = await active_webhook_secret(session, endpoint.id)
                    timestamp = int(time.time())
                    signature = sign_delivery_body(secret, timestamp, body)
                    webhook_delivery_total.inc()
                    response = await client.post(
                        endpoint.url,
                        content=body,
                        headers={
                            "content-type": "application/json",
                            "forgepay-signature": signature,
                            "forgepay-timestamp": str(timestamp),
                            "x-correlation-id": correlation_id,
                        },
                    )
                    delivery.attempts += 1
                    if 200 <= response.status_code < 300:
                        delivery.status = "SUCCEEDED"
                        sent += 1
                    elif (
                        delivery.attempts >= settings.webhook_max_attempts
                        or response.status_code < 500
                    ):
                        delivery.status = "DEAD_LETTER"
                        delivery.last_error = f"http {response.status_code}"
                        webhook_delivery_failures_total.inc()
                    else:
                        delivery.status = "RETRY"
                        webhook_delivery_failures_total.inc()
                        delivery.next_attempt_at = utc_now() + timedelta(
                            seconds=next_delay(delivery.attempts)
                        )
                except httpx.HTTPError as exc:
                    delivery.attempts += 1
                    webhook_delivery_failures_total.inc()
                    delivery.status = (
                        "DEAD_LETTER"
                        if delivery.attempts >= settings.webhook_max_attempts
                        else "RETRY"
                    )
                    if delivery.status == "RETRY":
                        delivery.next_attempt_at = utc_now() + timedelta(
                            seconds=next_delay(delivery.attempts)
                        )
                    delivery.last_error = str(exc)
    return sent


async def run_forever() -> None:
    while True:
        await dispatch_once()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_forever())
