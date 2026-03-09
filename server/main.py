"""WebReaper API Server — FastAPI backend for dashboard and agent gateway."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
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
from webreaper.billing import router as billing_router

configure_logging()
logger = get_logger("webreaper.server")

log_buffer = LogBuffer(max_size=1000)
metrics_service = MetricsService()
proxy_service = ProxyService()
repeater_service = RepeaterService()
intruder_service = IntruderService()

# Dev-only fallback origins used when CORS_ORIGINS is unset
_DEV_ORIGINS = [
    "http://localhost:3000", "http://localhost:5173",
    "http://127.0.0.1:3000", "tauri://localhost",
]


def _get_cors_origins() -> list[str]:
    """Read CORS origins from CORS_ORIGINS env var (comma-separated) or fall back to dev defaults."""
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    app_env = os.environ.get("APP_ENV", "production")
    if app_env == "production":
        logger.warning("cors.no_origins_configured", hint="Set CORS_ORIGINS env var for production")
    return _DEV_ORIGINS


def _validate_required_services():
    """Warn at startup if critical external services are not configured."""
    app_env = os.environ.get("APP_ENV", "production")
    missing = []
    if not os.environ.get("SUPABASE_URL"):
        missing.append("SUPABASE_URL")
    if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        msg = f"Auth will fail — missing: {', '.join(missing)}"
        if app_env == "production":
            logger.error("startup.missing_config", vars=missing)
            raise RuntimeError(msg)
        logger.warning("startup.missing_config", vars=missing, hint="Auth endpoints will return 500")

    if not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        logger.warning("startup.stripe_not_configured", hint="Billing webhooks will reject all events")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server startup/shutdown lifecycle."""
    logger.info("WebReaper API starting...")
    _validate_required_services()
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
    version="2.3.0",
    lifespan=lifespan,
)

# Rate limiter — default 60 requests/minute per IP.
# Override per-route with @limiter.limit() decorator.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
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
app.include_router(billing_router, prefix="/webhooks", tags=["billing"])


@app.get("/health")
async def health():
    result = {"status": "ok", "version": "2.3.0"}
    if app.state.db:
        try:
            async with app.state.db.get_session() as session:
                await session.execute(text("SELECT 1"))
            result["db"] = "ok"
        except Exception:
            result["status"] = "degraded"
            result["db"] = "unreachable"
    return result


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Entry point for running the server."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
