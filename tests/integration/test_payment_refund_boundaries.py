from uuid import uuid4

import httpx

from tests.integration.helpers import BASE_URL, create_funded_customer, create_merchant, reset_state


def test_partial_full_and_excess_refund_boundaries() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        _, headers = create_merchant(client)
        customer = create_funded_customer(client, headers)
        payment = client.post(
            "/api/v1/payments",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"customer_id": customer["customer_id"], "amount_minor": 1000, "currency": "PLN"},
        )
        payment.raise_for_status()
        payment_id = payment.json()["payment_id"]
        client.post(f"/api/v1/payments/{payment_id}/authorize", headers=headers).raise_for_status()
        client.post(f"/api/v1/payments/{payment_id}/capture", headers=headers).raise_for_status()

        partial = client.post(
            f"/api/v1/payments/{payment_id}/refund",
            headers=headers,
            json={"amount_minor": 400},
        )
        partial.raise_for_status()
        assert partial.json()["status"] == "PARTIALLY_REFUNDED"
        assert partial.json()["refunded_amount_minor"] == 400

        excessive = client.post(
            f"/api/v1/payments/{payment_id}/refund",
            headers=headers,
            json={"amount_minor": 700},
        )
        assert excessive.status_code == 409
        assert excessive.json()["detail"]["error"]["code"] == "REFUND_EXCEEDS_CAPTURE"

        final = client.post(
            f"/api/v1/payments/{payment_id}/refund",
            headers=headers,
            json={"amount_minor": 600},
        )
        final.raise_for_status()
        assert final.json()["status"] == "REFUNDED"
        assert final.json()["refunded_amount_minor"] == 1000
