from uuid import UUID

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, correlation_id: UUID) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "correlation_id": str(correlation_id)}},
    )
