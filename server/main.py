"""WebReaper API Server — FastAPI backend for dashboard and agent gateway."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from webreaper.database import get_db_manager
from webreaper.logging_config import configure_logging, get_logger
from server.routes import jobs, results, security, stream, chat, agents, workstation, license
from server.services.log_buffer import LogBuffer
from server.services.metrics import MetricsService

configure_logging()
logger = get_logger("webreaper.server")

log_buffer = LogBuffer(max_size=1000)
metrics_service = MetricsService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server startup/shutdown lifecycle."""
    logger.info("WebReaper API starting...")
    app.state.db = get_db_manager()
    if app.state.db:
        await app.state.db.init_async()
    app.state.log_buffer = log_buffer
    app.state.metrics = metrics_service
    app.state.active_jobs = {}
    yield
    logger.info("WebReaper API shutting down...")
    for job_id, job in app.state.active_jobs.items():
        logger.info(f"Cancelling job {job_id}")


app = FastAPI(
    title="WebReaper API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:5173",
        "http://127.0.0.1:3000", "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(security.router, prefix="/api/security", tags=["security"])
app.include_router(stream.router, prefix="/stream", tags=["streaming"])
app.include_router(chat.router, prefix="/ws", tags=["websocket"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(workstation.router, prefix="/api/workstation", tags=["workstation"])
app.include_router(license.router, prefix="/api/license", tags=["license"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Entry point for running the server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
