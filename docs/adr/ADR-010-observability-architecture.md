# ADR-010 Observability Architecture

## Context
Distributed failures require correlation across HTTP, workers, Kafka, and webhooks.

## Decision
Use correlation IDs, structured JSON logs, OpenTelemetry hooks, Prometheus metrics, and Grafana dashboards.

## Alternatives
Plain text logs only or vendor-specific tracing.

## Consequences
Operators can follow payment flows across components.

## Trade-offs
Local demo tracing is lighter than production collector/exporter setup.
