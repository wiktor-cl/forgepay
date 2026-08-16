from fastapi import FastAPI, Header, Request, Response
from forgepay_security.webhooks import verify_webhook

app = FastAPI(title="ForgePay Demo Webhook Receiver")
received: list[dict[str, object]] = []
attempts_by_path: dict[str, int] = {}
accepted_secrets: set[str] = {"dev-only-change-me"}


def signature_is_valid(signature: str, timestamp: int, body: bytes) -> bool:
    return any(verify_webhook(secret, signature, timestamp, body) for secret in accepted_secrets)


@app.post("/webhooks/forgepay")
async def receive(
    request: Request,
    forgepay_signature: str = Header(alias="ForgePay-Signature"),
    forgepay_timestamp: int = Header(alias="ForgePay-Timestamp"),
    x_correlation_id: str | None = Header(default=None, alias="x-correlation-id"),
) -> dict[str, str]:
    body = await request.body()
    if not signature_is_valid(forgepay_signature, forgepay_timestamp, body):
        return {"status": "invalid"}
    received.append(
        {"body": body.decode(), "signature": forgepay_signature, "correlation_id": x_correlation_id}
    )
    return {"status": "ok"}


@app.post("/webhooks/fail-then-ok/{failures}")
async def fail_then_ok(
    failures: int,
    request: Request,
    response: Response,
    forgepay_signature: str = Header(alias="ForgePay-Signature"),
    forgepay_timestamp: int = Header(alias="ForgePay-Timestamp"),
    x_correlation_id: str | None = Header(default=None, alias="x-correlation-id"),
) -> dict[str, str]:
    body = await request.body()
    if not signature_is_valid(forgepay_signature, forgepay_timestamp, body):
        response.status_code = 401
        return {"status": "invalid"}
    key = str(request.url.path)
    attempts_by_path[key] = attempts_by_path.get(key, 0) + 1
    if attempts_by_path[key] <= failures:
        response.status_code = 500
        return {"status": "temporary_failure"}
    received.append(
        {
            "body": body.decode(),
            "signature": forgepay_signature,
            "path": key,
            "correlation_id": x_correlation_id,
        }
    )
    return {"status": "ok"}


@app.post("/webhooks/always-fail")
async def always_fail(
    request: Request,
    response: Response,
    forgepay_signature: str = Header(alias="ForgePay-Signature"),
    forgepay_timestamp: int = Header(alias="ForgePay-Timestamp"),
) -> dict[str, str]:
    body = await request.body()
    if not signature_is_valid(forgepay_signature, forgepay_timestamp, body):
        response.status_code = 401
        return {"status": "invalid"}
    response.status_code = 500
    return {"status": "failed"}


@app.get("/received")
async def list_received() -> list[dict[str, object]]:
    return received


@app.post("/reset")
async def reset() -> dict[str, str]:
    received.clear()
    attempts_by_path.clear()
    accepted_secrets.clear()
    accepted_secrets.add("dev-only-change-me")
    return {"status": "reset"}


@app.post("/accepted-secrets")
async def add_secret(payload: dict[str, str]) -> dict[str, str]:
    accepted_secrets.add(payload["secret"])
    return {"status": "ok"}
