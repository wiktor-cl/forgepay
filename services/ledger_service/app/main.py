from fastapi import FastAPI

app = FastAPI(title="ForgePay Ledger Service")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}
