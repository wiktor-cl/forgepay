# ADR-002 Double-Entry Accounting

## Context
Mutable balances alone make audits and corrections fragile.

## Decision
Represent movement with immutable balanced journals and derive balances as projections.

## Alternatives
Single balance rows or event-only accounting.

## Consequences
Every movement has an auditable counterparty.

## Trade-offs
More tables and queries, but better correctness and explainability.
