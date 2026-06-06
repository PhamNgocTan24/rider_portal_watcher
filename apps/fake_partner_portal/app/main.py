import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = structlog.get_logger()

app = FastAPI(
    title="RidePortal Fake Partner Portal",
    description="Controlled fake portal for Playwright automation demos.",
    version="0.1.0",
)


@app.get("/health", response_class=JSONResponse, tags=["health"])
async def health() -> dict:
    """Basic health check — returns OK when the service is running."""
    return {"status": "ok", "service": "fake-portal"}
