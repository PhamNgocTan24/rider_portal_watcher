from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.routers import bookings, dashboard, logs, portal_status, rules

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run Alembic migrations on startup."""
    import asyncio
    from alembic import command
    from alembic.config import Config

    def _run() -> None:
        alembic_cfg = Config("/app/alembic.ini")
        command.upgrade(alembic_cfg, "head")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run)
    logger.info("migrations_complete")
    yield


app = FastAPI(
    title="RidePortal Watcher API",
    description="Automation backend for ride booking portal monitoring.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="/app/app/static"), name="static")
app.mount("/artifacts", StaticFiles(directory="/app/artifacts"), name="artifacts")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(bookings.router)
app.include_router(logs.router)
app.include_router(portal_status.router)
app.include_router(rules.router)
app.include_router(dashboard.router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", response_class=JSONResponse, tags=["health"])
async def health() -> dict:
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("db_health_check_failed", error=str(exc))
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": "api",
        "database": db_status,
    }
