from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from forgepay_observability.logging import configure_json_logging
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
from app.infra.models import Payment
from app.service import (
    BusinessError,
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
)

configure_json_logging()
app = FastAPI(title="ForgePay Payment Service", version="0.1.0")


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        raw = request.headers.get("x-correlation-id")
        request.state.correlation_id = UUID(raw) if raw else uuid4()
        response = await call_next(request)
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
    return await create_merchant(session, body, request.state.correlation_id)


@app.post("/api/v1/customers", status_code=201)
async def create_customer_route(
    request: Request,
    body: CustomerCreate,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("payments:write", request.state.correlation_id)
    return await create_customer(session, principal.merchant_id, body, request.state.correlation_id)


@app.post("/api/v1/accounts/{account_id}/fund", status_code=201)
async def fund_account_route(
    request: Request,
    account_id: UUID,
    body: FundAccountRequest,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    principal.require("payments:write", request.state.correlation_id)
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
    return await authorize_payment(
        session, principal.merchant_id, payment_id, request.state.correlation_id
    )


@app.post("/api/v1/payments/{payment_id}/capture")
async def capture_route(
    request: Request,
    payment_id: UUID,
    principal: Principal = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    principal.require("payments:write", request.state.correlation_id)
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
    return await register_webhook(
        session, principal.merchant_id, body, request.state.correlation_id
    )
