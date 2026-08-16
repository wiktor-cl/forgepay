import json
from uuid import uuid4

import httpx

BASE_URL = "http://localhost:8000"


def print_step(name: str, payload: object) -> None:
    print(f"\n== {name} ==")
    print(json.dumps(payload, indent=2))


def json_ok(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    return response.json()


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        merchant = json_ok(client.post("/api/v1/merchants", json={"name": "Demo Merchant"}))
        api_key = merchant["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}
        print_step("merchant", merchant)

        customer = json_ok(
            client.post(
                "/api/v1/customers",
                headers=headers,
                json={"email": "buyer@example.com", "currency": "PLN"},
            )
        )
        print_step("customer/account", customer)

        funding = json_ok(
            client.post(
                f"/api/v1/accounts/{customer['account_id']}/fund",
                headers=headers,
                json={"amount_minor": 10_000, "currency": "PLN"},
            )
        )
        print_step("funding journal", funding)

        idem = str(uuid4())
        payment_request = {
            "customer_id": customer["customer_id"],
            "amount_minor": 1000,
            "currency": "PLN",
        }
        payment = json_ok(
            client.post(
                "/api/v1/payments",
                headers={**headers, "Idempotency-Key": idem},
                json=payment_request,
            )
        )
        print_step("payment", payment)

        authorized = json_ok(
            client.post(f"/api/v1/payments/{payment['payment_id']}/authorize", headers=headers)
        )
        captured = json_ok(
            client.post(f"/api/v1/payments/{payment['payment_id']}/capture", headers=headers)
        )
        replay = json_ok(
            client.post(
                "/api/v1/payments",
                headers={**headers, "Idempotency-Key": idem},
                json=payment_request,
            )
        )
        print_step("authorized", authorized)
        print_step("captured", captured)
        print_step("idempotent replay", replay)


if __name__ == "__main__":
    main()
