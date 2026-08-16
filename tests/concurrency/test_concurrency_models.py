import asyncio


async def test_simulated_balance_gate_allows_only_available_funds() -> None:
    balance = 10_000
    lock = asyncio.Lock()
    successful = 0

    async def charge() -> None:
        nonlocal balance, successful
        async with lock:
            if balance >= 1000:
                balance -= 1000
                successful += 1

    await asyncio.gather(*(charge() for _ in range(50)))
    assert successful == 10
    assert balance == 0


async def test_simulated_idempotency_claim_creates_one_resource() -> None:
    created: dict[str, str] = {}
    lock = asyncio.Lock()

    async def create() -> str:
        async with lock:
            return created.setdefault("key", "payment_1")

    results = await asyncio.gather(*(create() for _ in range(50)))
    assert set(results) == {"payment_1"}
    assert len(created) == 1
