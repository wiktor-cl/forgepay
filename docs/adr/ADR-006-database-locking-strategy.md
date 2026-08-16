# ADR-006 Database Locking Strategy

## Context
Concurrent captures and charges must not double-spend.

## Decision
Use row locks for payment state transitions and unique constraints for one-time side effects.

## Alternatives
Distributed locks, optimistic-only version checks, or app-level mutexes.

## Consequences
Conflicts serialize where financial correctness requires it.

## Trade-offs
Hot rows can bottleneck, but behavior is clear and recoverable.
