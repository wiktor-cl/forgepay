from forgepay_security.webhooks import sign_webhook, verify_webhook


def test_webhook_signature_round_trip() -> None:
    body = b'{"event_id":"evt_1"}'
    signature = sign_webhook("secret", 123, body)
    assert verify_webhook("secret", signature, 123, body)
    assert not verify_webhook("secret", signature, 123, b"{}")
