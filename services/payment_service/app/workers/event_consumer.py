import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from app.infra.database import SessionFactory
from app.service import process_payment_event_for_webhooks
from app.settings import Settings
from forgepay_events import EventEnvelope
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def decode_event_payload(raw: bytes) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    envelope = EventEnvelope.model_validate(payload)
    if envelope.version != 1:
        raise ValueError(f"unsupported event version {envelope.version}")
    return envelope.model_dump(mode="json")


async def consume_forever() -> None:
    settings = Settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_events,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="forgepay-payment-events",
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        async for message in consumer:
            try:
                payload = decode_event_payload(message.value)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError):
                logger.exception("discarding invalid event payload")
                await consumer.commit()
                continue
            event_id = UUID(str(payload["event_id"]))
            event_type = str(payload["event_type"])
            async with SessionFactory() as session:
                async with session.begin():
                    await process_payment_event_for_webhooks(session, event_id, event_type, payload)
            await consumer.commit()
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(consume_forever())
