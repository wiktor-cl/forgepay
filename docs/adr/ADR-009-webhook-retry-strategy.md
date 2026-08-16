# ADR-009 Webhook Retry Strategy

## Context
Merchant endpoints are unreliable and should not block payment requests.

## Decision
Deliver webhooks asynchronously with HMAC signatures, bounded exponential backoff, jitter, status history, and dead-letter state.

## Alternatives
Synchronous delivery or infinite retry.

## Consequences
Merchants can replay dead-lettered events manually.

## Trade-offs
Delivery can lag behind payment state, but request latency and resiliency improve.
