from uuid import UUID

from app.api.errors import api_error
from app.infra.database import get_session
from app.infra.models import ApiKey
from fastapi import Depends, Header, Request
from forgepay_security.api_keys import hash_secret
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class Principal:
    def __init__(self, merchant_id: UUID, scopes: set[str]) -> None:
        self.merchant_id = merchant_id
        self.scopes = scopes

    def require(self, scope: str, correlation_id: UUID) -> None:
        if scope not in self.scopes:
            raise api_error(
                403, "INSUFFICIENT_SCOPE", "API key does not have required scope.", correlation_id
            )


async def require_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    correlation_id = request.state.correlation_id
    if not authorization or not authorization.startswith("Bearer "):
        raise api_error(401, "UNAUTHENTICATED", "Missing bearer API key.", correlation_id)
    digest = hash_secret(authorization.removeprefix("Bearer ").strip())
    key = await session.scalar(
        select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.revoked_at.is_(None))
    )
    if key is None:
        raise api_error(401, "UNAUTHENTICATED", "Invalid API key.", correlation_id)
    return Principal(merchant_id=key.merchant_id, scopes=set(key.scopes))
