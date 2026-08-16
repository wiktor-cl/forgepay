# Failure Recovery

## Kafka Unavailable

Payment commits still succeed because outbox rows are part of the database transaction. The
publisher increments retry counts and leaves rows pending until Kafka is available.

## Webhook Destination Returns 500

The webhook dispatcher stores attempt count, last error, and next attempt metadata. Transient
5xx/network errors are retried with bounded exponential backoff and jitter. 4xx responses are
treated as permanent unless the endpoint is manually replayed.

## Duplicate Kafka Event

Consumers insert into `processed_events` before performing side effects. The primary key
`(event_id, consumer_name)` makes duplicate processing a no-op.

## Crash After Commit Before Publish

The outbox row remains unpublished. On restart, the publisher reads rows where `published_at`
is null and resumes.

## Concurrent Capture

The payment row is selected `FOR UPDATE`. A unique journal reference for `payment_capture` also
prevents duplicate ledger side effects.

## Redis Unavailable

Redis-backed velocity windows may degrade risk scoring or rate limiting, but money correctness
does not depend on Redis.
