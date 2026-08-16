# System Overview

ForgePay is a simulated distributed payments platform. The payment service owns merchant-facing
API orchestration and transactional state changes. PostgreSQL owns financial truth. Kafka carries
events between workers. Redis is optional and never authoritative for money.

```mermaid
flowchart TB
  Client[Merchant API] --> API[FastAPI Payment Service]
  API --> DB[(PostgreSQL)]
  API --> Risk[Risk Service]
  DB --> Outbox[Outbox Publisher]
  Outbox --> Kafka[(Kafka)]
  Kafka --> Ledger[Ledger Consumer]
  Kafka --> Webhook[Webhook Worker]
  Webhook --> MerchantWebhook[Merchant Webhook Endpoint]
  API --> Metrics[Prometheus /metrics]
```

The main consistency boundary is a PostgreSQL transaction. Payment updates, audit rows, and
outbox events are committed atomically.
