import pytest
from app.domain.payment import PaymentStatus, PaymentTransitionError, transition


def test_payment_lifecycle_happy_path() -> None:
    status = transition(PaymentStatus.CREATED, PaymentStatus.PENDING)
    status = transition(status, PaymentStatus.AUTHORIZED)
    status = transition(status, PaymentStatus.CAPTURED)
    assert status == PaymentStatus.CAPTURED


def test_illegal_transition_is_rejected() -> None:
    with pytest.raises(PaymentTransitionError):
        transition(PaymentStatus.CREATED, PaymentStatus.CAPTURED)
