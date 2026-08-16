# Ledger

ForgePay uses double-entry journal entries with integer minor units. Balances are projections,
not the source of truth.

Rules:

- Every journal has at least two lines.
- Debits equal credits.
- A journal contains exactly one currency.
- Entries are append-only.
- Corrections are compensating entries, not updates to historical rows.

Important constraints are implemented in Alembic: positive amounts, valid directions, unique
journal reference, and immutable foreign key relationships.
