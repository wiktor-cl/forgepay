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
