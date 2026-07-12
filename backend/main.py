"""Tradzo FastAPI backend — entry point.

Run locally:
    uvicorn main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import broker, execution, health
from scheduler import shutdown_scheduler, start_scheduler
from services import firebase_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("tradzo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    firebase_service.init_firebase()
    start_scheduler()
    log.info("Tradzo backend started on port %s.", settings.port)
    yield
    # Shutdown
    shutdown_scheduler()
    log.info("Tradzo backend stopped.")


app = FastAPI(title="Tradzo Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(broker.router)
app.include_router(execution.router)


@app.get("/")
def root():
    return {"service": "tradzo-backend", "docs": "/docs", "health": "/health"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
