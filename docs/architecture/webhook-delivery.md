# Webhook Delivery

```mermaid
sequenceDiagram
  participant K as Kafka
  participant W as Webhook Worker
  participant DB as PostgreSQL
  participant E as Merchant Endpoint
  K->>W: payment.captured
  W->>DB: insert processed_events
  W->>DB: enqueue webhook_delivery
  W->>E: POST signed payload
  alt 2xx
    W->>DB: mark SUCCEEDED
  else 5xx/network
    W->>DB: schedule RETRY
  else permanent/max retries
    W->>DB: mark DEAD_LETTER
  end
```

Each webhook endpoint has a unique active signing secret encrypted at rest with the configured
master key. Plaintext is returned only when the endpoint is created or when the secret is rotated.
Deliveries are signed with the endpoint's active secret and include both `ForgePay-Timestamp` and
`ForgePay-Signature`; receivers can reject stale timestamps to reduce replay risk.

Manual replay moves a delivery back to `PENDING` and records an audit event. It does not reset the
attempt counter, so retry history remains visible.
