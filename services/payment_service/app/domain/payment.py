from enum import StrEnum


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentTransitionError(ValueError):
    def __init__(self, current: PaymentStatus, target: PaymentStatus) -> None:
        super().__init__(f"cannot transition payment from {current} to {target}")
        self.current = current
        self.target = target


_ALLOWED: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.CREATED: {PaymentStatus.PENDING, PaymentStatus.CANCELLED, PaymentStatus.FAILED},
    PaymentStatus.PENDING: {
        PaymentStatus.AUTHORIZED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.AUTHORIZED: {
        PaymentStatus.CAPTURED,
        PaymentStatus.CANCELLED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.CAPTURED: {PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED},
    PaymentStatus.PARTIALLY_REFUNDED: {PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED},
    PaymentStatus.REFUNDED: set(),
    PaymentStatus.FAILED: set(),
    PaymentStatus.CANCELLED: set(),
}


def transition(current: PaymentStatus, target: PaymentStatus) -> PaymentStatus:
    if target not in _ALLOWED[current]:
        raise PaymentTransitionError(current, target)
    return target
