# ADR-008 Redis Usage Boundaries

## Context
Redis is useful but unsuitable as the sole financial authority.

## Decision
Use Redis only for rate limiting, caches, and risk velocity windows.

## Alternatives
Redis-backed balances or distributed locks.

## Consequences
Redis loss may affect throttling or risk precision but not ledger correctness.

## Trade-offs
Some fast counters can be approximate; financial state remains durable.
