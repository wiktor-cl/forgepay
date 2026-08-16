from fastapi import FastAPI

app = FastAPI(title="ForgePay Webhook Service")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}
