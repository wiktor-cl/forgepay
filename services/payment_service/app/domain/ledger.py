from forgepay_common.money import LedgerLine, Money, assert_balanced


def simulated_funding(
    amount: Money, customer_account: str, funding_account: str
) -> list[LedgerLine]:
    lines = [
        LedgerLine(account=customer_account, direction="DEBIT", money=amount),
        LedgerLine(account=funding_account, direction="CREDIT", money=amount),
    ]
    assert_balanced(lines)
    return lines


def capture(amount: Money, customer_account: str, merchant_account: str) -> list[LedgerLine]:
    lines = [
        LedgerLine(account=merchant_account, direction="DEBIT", money=amount),
        LedgerLine(account=customer_account, direction="CREDIT", money=amount),
    ]
    assert_balanced(lines)
    return lines


def refund(amount: Money, merchant_account: str, customer_account: str) -> list[LedgerLine]:
    lines = [
        LedgerLine(account=customer_account, direction="DEBIT", money=amount),
        LedgerLine(account=merchant_account, direction="CREDIT", money=amount),
    ]
    assert_balanced(lines)
    return lines
