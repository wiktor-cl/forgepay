from fastapi import FastAPI, Header, Request
from forgepay_security.webhooks import verify_webhook

app = FastAPI(title="ForgePay Demo Webhook Receiver")
received: list[dict[str, object]] = []


@app.post("/webhooks/forgepay")
async def receive(
    request: Request,
    forgepay_signature: str = Header(alias="ForgePay-Signature"),
    forgepay_timestamp: int = Header(alias="ForgePay-Timestamp"),
) -> dict[str, str]:
    body = await request.body()
    if not verify_webhook("dev-only-change-me", forgepay_signature, forgepay_timestamp, body):
        return {"status": "invalid"}
    received.append({"body": body.decode(), "signature": forgepay_signature})
    return {"status": "ok"}


@app.get("/received")
async def list_received() -> list[dict[str, object]]:
    return received
