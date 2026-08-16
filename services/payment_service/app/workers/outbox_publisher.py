import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from app.infra.database import SessionFactory
from app.infra.repositories import bump_publish_retry, mark_published, pending_outbox
from app.settings import Settings
from forgepay_observability.metrics import outbox_pending_total, outbox_publish_failures_total

logger = logging.getLogger(__name__)


async def publish_once() -> int:
    settings = Settings()
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        await producer.start()
    except KafkaError as exc:
        logger.warning("kafka producer start failed: %s", exc)
        return 0
    count = 0
    try:
        async with SessionFactory() as session, session.begin():
            rows = await pending_outbox(session)
            outbox_pending_total.set(len(rows))
            for event in rows:
                try:
                    await producer.send_and_wait(
                        settings.kafka_topic_events,
                        json.dumps(event.payload, default=str).encode(),
                        key=str(event.event_id).encode(),
                    )
                    await mark_published(session, event)
                    count += 1
                except KafkaError as exc:
                    logger.warning(
                        "outbox publish failed: %s",
                        exc,
                        extra={"event_id": str(event.event_id)},
                    )
                    outbox_publish_failures_total.inc()
                    await bump_publish_retry(session, event)
    finally:
        await producer.stop()
    return count


async def run_forever() -> None:
    while True:
        await publish_once()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_forever())
