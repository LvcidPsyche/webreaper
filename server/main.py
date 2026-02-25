"""WebReaper API Server — FastAPI backend for dashboard and agent gateway."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from webreaper.database import get_db_manager
from webreaper.logging_config import configure_logging, get_logger
from webreaper.migrations import ensure_database_schema
from webreaper.proxy.service import ProxyService
from webreaper.repeater.service import RepeaterService
from webreaper.intruder.service import IntruderService
from server.routes import jobs, results, security, stream, chat, agents, workstation, license, data, analysis, workspaces, proxy, repeater, intruder, governance
from server.services.log_buffer import LogBuffer
from server.services.metrics import MetricsService

configure_logging()
logger = get_logger("webreaper.server")

log_buffer = LogBuffer(max_size=1000)
metrics_service = MetricsService()
proxy_service = ProxyService()
repeater_service = RepeaterService()
intruder_service = IntruderService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server startup/shutdown lifecycle."""
    logger.info("WebReaper API starting...")
    app.state.db = get_db_manager()
    if app.state.db:
        await app.state.db.init_async()
        await ensure_database_schema(app.state.db)
        try:
            interrupted = await app.state.db.mark_running_crawls_interrupted()
            if interrupted:
                logger.warning(f"Marked {interrupted} stale running crawl(s) as interrupted on startup")
        except Exception as e:
            logger.warning(f"Failed stale crawl recovery check: {e}")
    app.state.log_buffer = log_buffer
    app.state.metrics = metrics_service
    app.state.active_jobs = {}
    app.state.proxy_service = proxy_service
    app.state.repeater_service = repeater_service
    app.state.intruder_service = intruder_service
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
        "http://localhost:8765", "http://127.0.0.1:8765",
        "http://76.13.114.80:8765", "http://76.13.114.80",
        "http://76.13.114.80:4001",
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
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(proxy.router, prefix="/api/proxy", tags=["proxy"])
app.include_router(repeater.router, prefix="/api/repeater", tags=["repeater"])
app.include_router(intruder.router, prefix="/api/intruder", tags=["intruder"])
app.include_router(governance.router, prefix="/api/governance", tags=["governance"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Entry point for running the server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
