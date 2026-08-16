from enum import StrEnum

from pydantic import BaseModel, Field


class RiskDecision(StrEnum):
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


class RiskResult(BaseModel, frozen=True):
    score: float = Field(ge=0, le=1)
    decision: RiskDecision
    reasons: list[str]


def evaluate_risk(
    amount_minor: int,
    currency: str,
    merchant_risk_level: int = 1,
    velocity_count: int = 0,
    country_mismatch: bool = False,
) -> RiskResult:
    score = min(1.0, merchant_risk_level * 0.08 + velocity_count * 0.05)
    reasons: list[str] = []
    if amount_minor >= 100_000:
        score += 0.35
        reasons.append("HIGH_AMOUNT")
    if velocity_count >= 5:
        reasons.append("HIGH_VELOCITY")
    if currency not in {"PLN", "EUR", "USD"}:
        score += 0.25
        reasons.append("UNUSUAL_CURRENCY")
    if country_mismatch:
        score += 0.20
        reasons.append("COUNTRY_MISMATCH")
    score = min(score, 1.0)
    decision = RiskDecision.APPROVE
    if score >= 0.85:
        decision = RiskDecision.REJECT
    elif score >= 0.55:
        decision = RiskDecision.REVIEW
    return RiskResult(score=round(score, 2), decision=decision, reasons=reasons)
