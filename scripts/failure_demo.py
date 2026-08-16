import asyncio
from uuid import uuid4

import httpx

BASE_URL = "http://localhost:8000"


async def duplicate_request(api_key: str, customer_id: str) -> None:
    idem = str(uuid4())
    payload = {"customer_id": customer_id, "amount_minor": 1000, "currency": "PLN"}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/payments",
                    headers={"Authorization": f"Bearer {api_key}", "Idempotency-Key": idem},
                    json=payload,
                )
                for _ in range(50)
            ],
            return_exceptions=True,
        )
    bodies = [r.json() for r in responses if isinstance(r, httpx.Response)]
    print("duplicate request: expected 1 payment and 49 equivalent responses")
    print({"responses": len(bodies), "payment_ids": sorted({b["payment_id"] for b in bodies})})


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        merchant = (await client.post("/api/v1/merchants", json={"name": "Failure Demo"})).json()
        headers = {"Authorization": f"Bearer {merchant['api_key']}"}
        customer = (
            await client.post(
                "/api/v1/customers",
                headers=headers,
                json={"email": "chaos@example.com", "currency": "PLN"},
            )
        ).json()
        await client.post(
            f"/api/v1/accounts/{customer['account_id']}/fund",
            headers=headers,
            json={"amount_minor": 10_000, "currency": "PLN"},
        )
    await duplicate_request(merchant["api_key"], customer["customer_id"])
    print(
        "overspending/outbox/Kafka scenarios are documented in docs/architecture/failure-recovery.md"
    )


if __name__ == "__main__":
    asyncio.run(main())
