# ADR-003 Transactional Outbox

## Context
Publishing to Kafka inside request handling can fail after a database commit.

## Decision
Write outbox rows in the same PostgreSQL transaction as domain changes.

## Alternatives
2PC, best-effort publish, or Kafka-first writes.

## Consequences
Events are eventually published by a background worker.

## Trade-offs
At-least-once publication requires deduplication downstream.
