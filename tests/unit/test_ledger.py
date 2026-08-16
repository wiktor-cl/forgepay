import pytest
from forgepay_common.money import Currency, LedgerLine, Money, assert_balanced
from hypothesis import given
from hypothesis import strategies as st


@given(st.integers(min_value=1, max_value=10_000))
def test_balanced_journal_property(amount: int) -> None:
    lines = [
        LedgerLine(
            account="customer_cash",
            direction="DEBIT",
            money=Money(amount_minor=amount, currency=Currency.PLN),
        ),
        LedgerLine(
            account="merchant_receivable",
            direction="CREDIT",
            money=Money(amount_minor=amount, currency=Currency.PLN),
        ),
    ]
    assert_balanced(lines)


def test_unbalanced_journal_rejected() -> None:
    with pytest.raises(ValueError, match="balanced"):
        assert_balanced(
            [
                LedgerLine(
                    account="a",
                    direction="DEBIT",
                    money=Money(amount_minor=100, currency=Currency.PLN),
                ),
                LedgerLine(
                    account="b",
                    direction="CREDIT",
                    money=Money(amount_minor=99, currency=Currency.PLN),
                ),
            ]
        )


def test_cross_currency_journal_rejected() -> None:
    with pytest.raises(ValueError, match="cross-currency"):
        assert_balanced(
            [
                LedgerLine(
                    account="a",
                    direction="DEBIT",
                    money=Money(amount_minor=100, currency=Currency.PLN),
                ),
                LedgerLine(
                    account="b",
                    direction="CREDIT",
                    money=Money(amount_minor=100, currency=Currency.EUR),
                ),
            ]
        )
