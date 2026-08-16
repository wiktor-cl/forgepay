import asyncio

import httpx
from forgepay_security.api_keys import hash_secret

from tests.integration.helpers import BASE_URL, create_merchant, reset_state
from tests.integration.test_payment_failures_and_ledger_invariants import _execute_sql


def test_unknown_api_key_is_rejected() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        response = client.post(
            "/api/v1/customers",
            headers={"Authorization": "Bearer fg_test_unknown"},
            json={"email": "security@example.com", "currency": "PLN"},
        )
    assert response.status_code == 401


def test_revoked_api_key_is_rejected() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        api_key, headers = create_merchant(client)
        asyncio.run(
            _execute_sql(
                """
                update api_keys
                set revoked_at = now()
                where key_hash = $1
                """,
                hash_secret(api_key),
            )
        )
        response = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"email": "revoked@example.com", "currency": "PLN"},
        )
    assert response.status_code == 401


def test_wrong_scope_is_rejected() -> None:
    reset_state()
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        api_key, headers = create_merchant(client)
        asyncio.run(
            _execute_sql(
                """
                update api_keys
                set scopes = '["payments:read"]'::jsonb
                where key_hash = $1
                """,
                hash_secret(api_key),
            )
        )
        response = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"email": "scope@example.com", "currency": "PLN"},
        )
    assert response.status_code == 403
