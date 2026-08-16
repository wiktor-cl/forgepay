from locust import HttpUser, between, task


class PaymentUser(HttpUser):
    wait_time = between(0.2, 1.0)
    api_key = ""
    customer_id = ""

    @task(3)
    def create_payment(self) -> None:
        if not self.api_key or not self.customer_id:
            return
        self.client.post(
            "/api/v1/payments",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Idempotency-Key": "locust-${__VU}",
            },
            json={"customer_id": self.customer_id, "amount_minor": 1000, "currency": "PLN"},
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health/live")
