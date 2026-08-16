# Engineering Deep Dive

## PostgreSQL As Financial Source Of Truth

ForgePay keeps payment state, idempotency records, ledger journals, audit logs, and outbox rows in
PostgreSQL. That keeps the correctness boundary small: money-changing API calls either commit the
state change and its event together or commit nothing.

## Locking Strategy

Payment mutations select the payment row `FOR UPDATE`. Capture also locks the customer before
projecting available balance, so simultaneous captures serialize around the balance owner. Duplicate
financial postings are additionally blocked by the unique journal reference constraint.

## Why Exactly-Once Is Not Claimed

Kafka delivery and worker execution are treated as at-least-once. Consumers write a
`processed_events` inbox row in the same transaction as their side effects. Duplicate delivery is
therefore expected and safe, but not described as exactly-once across DB, Kafka, and HTTP webhooks.

## Transactional Outbox

Payment mutations append outbox rows inside the same DB transaction as payment state. If Kafka is
down after the DB commit, the row remains unpublished. The publisher later locks pending rows with
`SKIP LOCKED`, publishes them, and marks `published_at`.

## Idempotency Under Concurrent Retries

Payment creation claims `(merchant_id, idempotency_key)` with PostgreSQL `ON CONFLICT DO NOTHING`
and row locking. The first request stores the response body; concurrent identical requests return
the same payment id, while the same key with a different payload is rejected.

## Duplicate Events

The event consumer validates the event envelope and inserts `(event_id, consumer_name)` before
creating webhook deliveries. That insert and the side effect share one transaction, so duplicates do
not create duplicate deliveries.

## Webhook Delivery

Webhook delivery is asynchronous because merchant endpoints are outside the payment transaction.
Each endpoint has its own encrypted active signing secret. Deliveries use HMAC with timestamp,
bounded HTTP timeout, bounded exponential backoff plus jitter, terminal DLQ state, and audited
manual replay.

## Failure Behavior

Kafka unavailable: payments still commit; outbox rows remain pending. Redis unavailable: financial
correctness is unaffected. Webhook receiver failures: attempts and errors persist until success or
DLQ. Invalid Kafka messages are discarded without business side effects.

## High-Scale Redesign Points

At much higher scale, the balance projection would likely move to materialized account balances with
strict posting transactions, Kafka partitions would be keyed by aggregate/merchant, and webhook
dispatch would need per-merchant rate controls plus a durable scheduler. The portfolio version keeps
the implementation smaller so the correctness mechanisms are easy to inspect.
