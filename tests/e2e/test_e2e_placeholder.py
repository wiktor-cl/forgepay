import os

import pytest


@pytest.mark.e2e
def test_e2e_placeholder_requires_compose_stack() -> None:
    if os.getenv("FORGEPAY_E2E_BASE_URL") is None:
        pytest.skip("Start docker compose and set FORGEPAY_E2E_BASE_URL to run the smoke test.")
