import asyncio
import json
import time
from uuid import UUID

import httpx
from forgepay_security.webhooks import verify_webhook

from tests.integration.helpers import BASE_URL, create_merchant, fetch_all, fetch_row, reset_state


def test_webhook_endpoints_get_unique_non_retrievable_secrets() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        first = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={"url": "http://webhook-receiver-demo:8010/webhooks/forgepay", "event_types": []},
        )
        second = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={"url": "http://webhook-receiver-demo:8010/webhooks/forgepay", "event_types": []},
        )
        first.raise_for_status()
        second.raise_for_status()

    first_body = first.json()
    second_body = second.json()
    assert first_body["signing_secret"].startswith("whsec_")
    assert first_body["signing_secret"] != second_body["signing_secret"]
    rows = asyncio.run(fetch_all("select secret_ciphertext, secret_hash from webhook_secrets"))
    assert len(rows) == 2
    assert all(first_body["signing_secret"] not in row["secret_ciphertext"] for row in rows)
    assert all(second_body["signing_secret"] not in row["secret_ciphertext"] for row in rows)


def test_webhook_secret_rotation_retires_old_secret_and_activates_new_secret() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        created = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={"url": "http://webhook-receiver-demo:8010/webhooks/forgepay", "event_types": []},
        )
        created.raise_for_status()
        rotated = client.post(
            f"/api/v1/webhooks/endpoints/{created.json()['endpoint_id']}/rotate-secret",
            headers=headers,
        )
        rotated.raise_for_status()

    assert created.json()["signing_secret"] != rotated.json()["signing_secret"]
    rows = asyncio.run(
        fetch_all(
            """
            select version, active, retired_at is not null as retired
            from webhook_secrets
            where endpoint_id=$1
            order by version
            """,
            UUID(created.json()["endpoint_id"]),
        )
    )
    assert [(row["version"], row["active"], row["retired"]) for row in rows] == [
        (1, False, True),
        (2, True, False),
    ]


def test_endpoint_active_secret_validates_signature_and_other_secret_does_not() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        first = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={"url": "http://webhook-receiver-demo:8010/webhooks/forgepay", "event_types": []},
        )
        second = client.post(
            "/api/v1/webhooks/endpoints",
            headers=headers,
            json={"url": "http://webhook-receiver-demo:8010/webhooks/forgepay", "event_types": []},
        )
        first.raise_for_status()
        second.raise_for_status()

    event_id = "evt_test"
    body = json.dumps({"event_id": event_id}, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = asyncio.run(
        fetch_row(
            """
            select ws.secret_ciphertext
            from webhook_secrets ws
            where ws.endpoint_id=$1 and ws.active
            """,
            UUID(first.json()["endpoint_id"]),
        )
    )
    assert signature is not None
    from forgepay_security.webhooks import sign_webhook

    signed = sign_webhook(first.json()["signing_secret"], timestamp, body)
    assert verify_webhook(first.json()["signing_secret"], signed, timestamp, body)
    assert not verify_webhook(second.json()["signing_secret"], signed, timestamp, body)
