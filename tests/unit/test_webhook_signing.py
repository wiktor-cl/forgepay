import time

from forgepay_security.webhooks import sign_webhook, verify_webhook


def test_webhook_signature_round_trip() -> None:
    body = b'{"event_id":"evt_1"}'
    timestamp = int(time.time())
    signature = sign_webhook("secret", timestamp, body)
    assert verify_webhook("secret", signature, timestamp, body)
    assert not verify_webhook("secret", signature, timestamp, b"{}")


def test_webhook_signature_rejects_stale_timestamp() -> None:
    body = b'{"event_id":"evt_1"}'
    timestamp = int(time.time()) - 301
    signature = sign_webhook("secret", timestamp, body)
    assert not verify_webhook("secret", signature, timestamp, body)
