# ADR-010 Observability Architecture

## Context
Distributed failures require correlation across HTTP, workers, Kafka, and webhooks.

## Decision
Use correlation IDs, structured JSON logs, FastAPI OpenTelemetry instrumentation, Prometheus
metrics, and Grafana dashboards. Event envelopes carry `correlation_id`, and webhook delivery
forwards that value as `x-correlation-id`.

## Alternatives
Plain text logs only or vendor-specific tracing.

## Consequences
Operators can follow payment flows across components by correlation ID. Local tracing is
request-level only until a production collector/exporter setup is added.

## Trade-offs
Local demo tracing is lighter than production collector/exporter setup.
