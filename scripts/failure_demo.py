import subprocess
import sys

SCENARIOS = {
    "idempotency_50_concurrent_requests": [
        "tests/integration/test_real_postgres_concurrency.py::test_concurrent_identical_idempotent_requests_create_one_payment"
    ],
    "overspending_concurrent_captures": [
        "tests/integration/test_real_postgres_concurrency.py::test_concurrent_overspending_preserves_ledger_balance"
    ],
    "duplicate_event_one_side_effect": [
        "tests/resilience/test_outbox_kafka_webhooks.py::test_duplicate_kafka_event_creates_one_webhook_side_effect"
    ],
    "kafka_outage_outbox_recovery": [
        "tests/resilience/test_outbox_kafka_webhooks.py::test_kafka_outage_leaves_outbox_pending_then_recovers"
    ],
    "webhook_retry_dlq_replay": [
        "tests/resilience/test_outbox_kafka_webhooks.py::test_webhook_retry_dead_letter_and_manual_replay"
    ],
}


def main() -> int:
    failures = 0
    for name, tests in SCENARIOS.items():
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], check=False)
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"{name}: {status}", flush=True)
        failures += int(result.returncode != 0)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
