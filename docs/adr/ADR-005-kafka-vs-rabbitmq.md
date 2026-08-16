# ADR-005 Kafka vs RabbitMQ

## Context
Payment events need replayability and durable event streams.

## Decision
Use Kafka in the main architecture.

## Alternatives
RabbitMQ or a database-only queue.

## Consequences
Operational complexity is higher, but event replay and consumer groups are natural.

## Trade-offs
RabbitMQ may be simpler for command queues; Kafka better demonstrates stream-oriented consumers.
