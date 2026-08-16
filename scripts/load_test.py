from uuid import uuid4

from locust import HttpUser, between, task


class PaymentUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        merchant = self.client.post("/api/v1/merchants", json={"name": "Locust Merchant"})
        merchant.raise_for_status()
        self.headers = {"Authorization": f"Bearer {merchant.json()['api_key']}"}
        customer = self.client.post(
            "/api/v1/customers",
            headers=self.headers,
            json={"email": f"locust-{uuid4()}@example.com", "currency": "PLN"},
        )
        customer.raise_for_status()
        self.customer_id = customer.json()["customer_id"]
        account_id = customer.json()["account_id"]
        funding = self.client.post(
            f"/api/v1/accounts/{account_id}/fund",
            headers=self.headers,
            json={"amount_minor": 1_000_000, "currency": "PLN"},
        )
        funding.raise_for_status()
        self.last_payment_id: str | None = None

    @task(3)
    def create_payment(self) -> None:
        response = self.client.post(
            "/api/v1/payments",
            headers={**self.headers, "Idempotency-Key": str(uuid4())},
            json={"customer_id": self.customer_id, "amount_minor": 1000, "currency": "PLN"},
        )
        if response.status_code == 201:
            self.last_payment_id = response.json()["payment_id"]

    @task(1)
    def read_payment(self) -> None:
        if self.last_payment_id is not None:
            self.client.get(f"/api/v1/payments/{self.last_payment_id}", headers=self.headers)

    @task(1)
    def authorize_and_capture(self) -> None:
        payment = self.client.post(
            "/api/v1/payments",
            headers={**self.headers, "Idempotency-Key": str(uuid4())},
            json={"customer_id": self.customer_id, "amount_minor": 1000, "currency": "PLN"},
        )
        if payment.status_code != 201:
            return
        payment_id = payment.json()["payment_id"]
        authorized = self.client.post(
            f"/api/v1/payments/{payment_id}/authorize", headers=self.headers
        )
        if authorized.status_code == 200:
            self.client.post(f"/api/v1/payments/{payment_id}/capture", headers=self.headers)
