from prometheus_client import Counter, Gauge, Histogram

payments_created_total = Counter("payments_created_total", "Payments created")
payments_failed_total = Counter("payments_failed_total", "Payments failed")
payment_processing_duration_seconds = Histogram(
    "payment_processing_duration_seconds", "Payment processing duration"
)
outbox_pending_total = Gauge("outbox_pending_total", "Pending outbox rows")
outbox_publish_failures_total = Counter("outbox_publish_failures_total", "Outbox publish failures")
webhook_delivery_total = Counter("webhook_delivery_total", "Webhook delivery attempts")
webhook_delivery_failures_total = Counter(
    "webhook_delivery_failures_total", "Webhook delivery failures"
)
kafka_consumer_lag = Gauge("kafka_consumer_lag", "Kafka consumer lag")
http_request_duration_seconds = Histogram("http_request_duration_seconds", "HTTP request duration")
