from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import router as approval_requests_router
from app.core.config import settings
from app.db.session import SessionLocal

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready"}


app.include_router(approval_requests_router)
