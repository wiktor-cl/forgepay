# Events

Events use a versioned envelope:

```json
{
  "event_id": "...",
  "event_type": "payment.captured",
  "occurred_at": "...",
  "correlation_id": "...",
  "causation_id": "...",
  "aggregate_id": "...",
  "aggregate_type": "payment",
  "version": 1,
  "payload": {}
}
```

Schema evolution strategy:

- Add optional fields first.
- Keep existing meanings stable.
- Bump `version` for breaking payload changes.
- Keep consumers tolerant of unknown fields.
- Contract tests validate required metadata.

Consumers validate known event types and `version == 1`. Invalid or unsupported messages are
discarded before business side effects. ForgePay claims at-least-once delivery plus idempotent
processing, not exactly-once delivery across PostgreSQL, Kafka, and HTTP.
