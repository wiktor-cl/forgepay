from uuid import uuid4

from forgepay_events import EventEnvelope, EventType


def test_event_contract_contains_required_metadata() -> None:
    event = EventEnvelope(
        event_type=EventType.PAYMENT_CAPTURED,
        correlation_id=uuid4(),
        aggregate_id=uuid4(),
        aggregate_type="payment",
        payload={"payment_id": str(uuid4())},
    )
    payload = event.model_dump(mode="json")
    for field in [
        "event_id",
        "event_type",
        "occurred_at",
        "correlation_id",
        "aggregate_id",
        "aggregate_type",
        "version",
        "payload",
    ]:
        assert field in payload
