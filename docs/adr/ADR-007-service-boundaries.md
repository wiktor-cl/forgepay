# ADR-007 Service Boundaries

## Context
Microservices should exist only where ownership and scaling boundaries are defensible.

## Decision
Keep payment orchestration central while separating risk, ledger consumption, and webhook delivery concerns.

## Alternatives
A single monolith or many tiny CRUD services.

## Consequences
The demo remains understandable while exercising distributed patterns.

## Trade-offs
Some services are thin in the portfolio version; the boundary documents future scaling paths.
