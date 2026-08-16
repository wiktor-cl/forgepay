# ADR-007 Service Boundaries

## Context
Microservices should exist only where ownership and scaling boundaries are defensible.

## Decision
Keep payment orchestration central. The runtime has one primary payment service plus workers for
outbox publishing, payment-event consumption, and webhook delivery. The risk, ledger, and webhook
HTTP services in this portfolio are intentionally thin demo/readiness boundaries, not independent
business-owning microservices.

## Alternatives
A single monolith or many tiny CRUD services.

## Consequences
The demo remains understandable while exercising distributed patterns where they matter: outbox,
Kafka, idempotent consumption, and asynchronous webhooks.

## Trade-offs
The architecture is smaller than a full payment processor. That is intentional: fake service
decomposition would make the project harder to review without improving correctness.
