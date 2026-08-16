# Performance Smoke Test

This is a local smoke measurement, not a production benchmark.

Environment:

- Date: 2026-08-16
- Machine: local Windows workstation running Docker Desktop
- App stack: Docker Compose PostgreSQL, Redis, Kafka, payment service, workers
- Load tool: Locust 2.46.3

Command:

```bash
python -m locust -f scripts/load_test.py --headless -u 3 -r 3 -t 10s --host http://localhost:8000 --only-summary
```

Result:

- Users: 3
- Duration limit: 10 seconds
- Requests: 57
- Failures: 0
- Aggregated average latency: 45 ms
- Aggregated median latency: 56 ms
- Aggregated p95 latency: 86 ms
- Aggregated p99 latency: 97 ms
- Aggregate throughput: 8.66 requests/second

Covered traffic:

- Merchant/customer/account setup
- Payment create
- Payment read
- Payment authorize
- Payment capture

Interpretation:

The result is useful only as a reproducible local smoke check that the main API paths remain
responsive under small concurrent load. It should not be read as a capacity claim.
