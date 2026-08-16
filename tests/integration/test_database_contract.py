import os

import pytest


@pytest.mark.integration
def test_integration_placeholder_documents_container_requirement() -> None:
    if os.getenv("FORGEPAY_RUN_CONTAINERS") != "1":
        pytest.skip("Set FORGEPAY_RUN_CONTAINERS=1 to run Testcontainers-backed checks.")
