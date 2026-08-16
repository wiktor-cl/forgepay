# ADR-001 PostgreSQL as Financial Source of Truth

## Context
Money invariants require durable constraints and transactional isolation.

## Decision
Use PostgreSQL as the source of truth for payments, idempotency, ledger, outbox, inbox, and audit logs.

## Alternatives
Redis locks, Kafka compacted topics, or per-service local databases.

## Consequences
Database contention must be managed carefully, but correctness is easier to prove.

## Trade-offs
Lower theoretical write scalability than fully partitioned stores; much stronger local invariants.
