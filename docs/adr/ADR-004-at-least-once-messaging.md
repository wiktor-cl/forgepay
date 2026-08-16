# ADR-004 At-Least-Once Messaging

## Context
Kafka and HTTP webhooks can deliver duplicates.

## Decision
Consumers use inbox deduplication keyed by event ID and consumer name.

## Alternatives
Pretend exactly-once, global distributed transactions, or ignore duplicates.

## Consequences
Side effects must be idempotent.

## Trade-offs
Extra storage and checks for much better failure behavior.
