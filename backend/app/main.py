from fastapi import FastAPI

from app.api import auth_dev

app = FastAPI(title="AI Fitness Trainer Backend", version="0.1.0")
app.include_router(auth_dev.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
