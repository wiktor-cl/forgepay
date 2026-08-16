from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Currency(StrEnum):
    PLN = "PLN"
    EUR = "EUR"
    USD = "USD"


class Money(BaseModel, frozen=True):
    amount_minor: int = Field(gt=0)
    currency: Currency

    def ensure_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError("cross-currency movement is not supported")

    def __add__(self, other: "Money") -> "Money":
        self.ensure_same_currency(other)
        return Money(amount_minor=self.amount_minor + other.amount_minor, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self.ensure_same_currency(other)
        value = self.amount_minor - other.amount_minor
        if value < 0:
            raise ValueError("money cannot become negative")
        return Money(amount_minor=value, currency=self.currency)


class LedgerLine(BaseModel, frozen=True):
    account: str
    direction: str
    money: Money

    @model_validator(mode="after")
    def validate_direction(self) -> "LedgerLine":
        if self.direction not in {"DEBIT", "CREDIT"}:
            raise ValueError("direction must be DEBIT or CREDIT")
        return self


def assert_balanced(lines: list[LedgerLine]) -> None:
    if len(lines) < 2:
        raise ValueError("a journal needs at least two lines")
    currencies = {line.money.currency for line in lines}
    if len(currencies) != 1:
        raise ValueError("cross-currency journal entries are rejected")
    debits = sum(line.money.amount_minor for line in lines if line.direction == "DEBIT")
    credits = sum(line.money.amount_minor for line in lines if line.direction == "CREDIT")
    if debits != credits:
        raise ValueError("journal is not balanced")
