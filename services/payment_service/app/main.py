import time
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from forgepay_observability.logging import configure_json_logging
from forgepay_observability.metrics import http_request_duration_seconds
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import Principal, require_api_key
from app.api.errors import api_error
from app.api.schemas import (
    CustomerCreate,
    FundAccountRequest,
    MerchantCreate,
    PaymentCreate,
    RefundRequest,
    WebhookEndpointCreate,
)
from app.domain.payment import PaymentTransitionError
from app.infra.database import engine, get_session
from app.infra.models import Payment, WebhookDelivery, WebhookEndpoint
from app.infra.repositories import append_audit
from app.service import (
    BusinessError,
    PersistedBusinessError,
    authorize_payment,
    cancel_payment,
    capture_payment,
    create_customer,
    create_merchant,
    create_payment,
    fund_account,
    payment_response,
    refund_payment,
    register_webhook,
    rotate_webhook_secret,
)

configure_json_logging()
app = FastAPI(title="ForgePay Payment Service", version="0.1.0")
FastAPIInstrumentor.instrument_app(app)


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        raw = request.headers.get("x-correlation-id")
        request.state.correlation_id = UUID(raw) if raw else uuid4()
        started = time.perf_counter()
        response = await call_next(request)
        http_request_duration_seconds.observe(time.perf_counter() - started)
        response.headers["x-correlation-id"] = str(request.state.correlation_id)
        return response


app.add_middleware(CorrelationMiddleware)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError) -> Response:
    raise api_error(409, exc.code, exc.message, request.state.correlation_id)


@app.exception_handler(PaymentTransitionError)
async def transition_error_handler(request: Request, exc: PaymentTransitionError) -> Response:
    raise api_error(409, "ILLEGAL_PAYMENT_TRANSITION", str(exc), request.state.correlation_id)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("select 1"))
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/merchants", status_code=201)
async def create_merchant_route(
    request: Request, body: MerchantCreate, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    async with session.begin():
        return await create_merchant(session, body, request.state.correlation_id)


@app.post("/api/v1/customers", status_code=201)
async def create_customer_route(
    request: Request,
    body: CustomerCreate,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("payments:write", request.state.correlation_id)
    async with session.begin():
        return await create_customer(
            session, principal.merchant_id, body, request.state.correlation_id
        )


@app.post("/api/v1/accounts/{account_id}/fund", status_code=201)
async def fund_account_route(
    request: Request,
    account_id: UUID,
    body: FundAccountRequest,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("payments:write", request.state.correlation_id)
    async with session.begin():
        return await fund_account(
            session, principal.merchant_id, account_id, body, request.state.correlation_id
        )


@app.post("/api/v1/payments", status_code=201)
async def create_payment_route(
    request: Request,
    body: PaymentCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    principal.require("payments:write", request.state.correlation_id)
    async with session.begin():
        status, response_body = await create_payment(
            session, principal.merchant_id, body, idempotency_key, request.state.correlation_id
        )
    return JSONResponse(content=response_body, status_code=status)


@app.get("/api/v1/payments/{payment_id}")
async def get_payment_route(
    request: Request,
    payment_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    principal.require("payments:read", request.state.correlation_id)
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.merchant_id != principal.merchant_id:
        raise api_error(
            404, "PAYMENT_NOT_FOUND", "Payment was not found.", request.state.correlation_id
        )
    return payment_response(payment)


@app.post("/api/v1/payments/{payment_id}/authorize")
async def authorize_route(
    request: Request,
    payment_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    principal.require("payments:write", request.state.correlation_id)
    persisted_error: PersistedBusinessError | None = None
    async with session.begin():
        try:
            return await authorize_payment(
                session, principal.merchant_id, payment_id, request.state.correlation_id
            )
        except PersistedBusinessError as exc:
            persisted_error = exc
    if persisted_error is not None:
        raise api_error(
            409,
            persisted_error.code,
            persisted_error.message,
            request.state.correlation_id,
        )
    raise RuntimeError("authorize route exited without response")


@app.post("/api/v1/payments/{payment_id}/capture")
async def capture_route(
    request: Request,
    payment_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    principal.require("payments:write", request.state.correlation_id)
    async with session.begin():
        return await capture_payment(
            session, principal.merchant_id, payment_id, request.state.correlation_id
        )


@app.post("/api/v1/payments/{payment_id}/cancel")
async def cancel_route(
    request: Request,
    payment_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    principal.require("payments:write", request.state.correlation_id)
    async with session.begin():
        return await cancel_payment(
            session, principal.merchant_id, payment_id, request.state.correlation_id
        )


@app.post("/api/v1/payments/{payment_id}/refund")
async def refund_route(
    request: Request,
    payment_id: UUID,
    body: RefundRequest,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    principal.require("refunds:write", request.state.correlation_id)
    async with session.begin():
        return await refund_payment(
            session, principal.merchant_id, payment_id, body, request.state.correlation_id
        )


@app.post("/api/v1/webhooks/endpoints", status_code=201)
async def register_webhook_route(
    request: Request,
    body: WebhookEndpointCreate,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("webhooks:manage", request.state.correlation_id)
    async with session.begin():
        return await register_webhook(
            session, principal.merchant_id, body, request.state.correlation_id
        )


@app.post("/api/v1/webhooks/endpoints/{endpoint_id}/rotate-secret")
async def rotate_webhook_secret_route(
    request: Request,
    endpoint_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("webhooks:manage", request.state.correlation_id)
    async with session.begin():
        return await rotate_webhook_secret(
            session, principal.merchant_id, endpoint_id, request.state.correlation_id
        )


@app.post("/api/v1/webhooks/deliveries/{delivery_id}/replay")
async def replay_webhook_delivery_route(
    request: Request,
    delivery_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("webhooks:manage", request.state.correlation_id)
    async with session.begin():
        delivery = await session.get(WebhookDelivery, delivery_id, with_for_update=True)
        if delivery is None:
            raise api_error(
                404,
                "WEBHOOK_DELIVERY_NOT_FOUND",
                "Webhook delivery was not found.",
                request.state.correlation_id,
            )
        endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
        if endpoint is None or endpoint.merchant_id != principal.merchant_id:
            raise api_error(
                404,
                "WEBHOOK_DELIVERY_NOT_FOUND",
                "Webhook delivery was not found.",
                request.state.correlation_id,
            )
        delivery.status = "PENDING"
        delivery.next_attempt_at = None
        delivery.last_error = "manual replay requested"
        await append_audit(
            session,
            actor=f"merchant:{principal.merchant_id}",
            action="webhook.delivery_replayed",
            resource=f"webhook_delivery:{delivery.id}",
            correlation_id=request.state.correlation_id,
            metadata={"attempts": delivery.attempts},
        )
        return {"delivery_id": str(delivery.id), "status": delivery.status}
