# Ledger

ForgePay uses double-entry journal entries with integer minor units. Balances are projections,
not the source of truth.

Rules:

- Every journal has at least two lines.
- Debits equal credits.
- A journal contains exactly one currency.
- Posted entries are immutable.
- Corrections are compensating entries, not updates to historical rows.

PostgreSQL guarantees positive amounts, valid directions, unique financial references, posted
journal balance, single-currency posted journals, and immutability of posted journals/entries.
The domain layer guarantees that journals are created through a controlled DRAFT -> POSTED posting
function and that money uses integer minor units instead of floats.
