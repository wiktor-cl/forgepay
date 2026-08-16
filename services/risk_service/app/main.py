from typing import Any

from app.domain.risk import RiskResult, evaluate_risk
from fastapi import FastAPI

app = FastAPI(title="ForgePay Risk Service")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@app.post("/api/v1/risk/evaluate")
async def evaluate(payload: dict[str, Any]) -> RiskResult:
    return evaluate_risk(
        amount_minor=int(payload["amount_minor"]),
        currency=str(payload["currency"]),
        merchant_risk_level=int(payload.get("merchant_risk_level", 1)),
        velocity_count=int(payload.get("velocity_count", 0)),
        country_mismatch=bool(payload.get("country_mismatch", False)),
    )
