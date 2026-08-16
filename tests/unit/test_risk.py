from app.domain.risk import RiskDecision, evaluate_risk


def test_low_risk_payment_is_approved() -> None:
    result = evaluate_risk(1000, "PLN", merchant_risk_level=1)
    assert result.decision == RiskDecision.APPROVE


def test_high_velocity_large_payment_goes_to_review_or_reject() -> None:
    result = evaluate_risk(200_000, "PLN", merchant_risk_level=5, velocity_count=8)
    assert result.decision in {RiskDecision.REVIEW, RiskDecision.REJECT}
    assert "HIGH_AMOUNT" in result.reasons
    assert "HIGH_VELOCITY" in result.reasons
