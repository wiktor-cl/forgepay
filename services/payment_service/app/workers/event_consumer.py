import asyncio
import json
import logging
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from app.infra.database import SessionFactory
from app.service import process_payment_event_for_webhooks
from app.settings import Settings

logger = logging.getLogger(__name__)


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
            payload = json.loads(message.value.decode("utf-8"))
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
