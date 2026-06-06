"""
Worker entry point.

Task 1 skeleton: logs startup message and exits cleanly.
Full polling loop will be implemented in Task 8.
"""
import asyncio
import structlog

from app.config import settings

logger = structlog.get_logger()


async def main() -> None:
    logger.info(
        "worker_start",
        api_base_url=settings.api_base_url,
        fake_portal_base_url=settings.fake_portal_base_url,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        headless=settings.worker_headless,
    )
    logger.info("worker_idle", message="Worker skeleton running. Polling not yet implemented (Task 8).")

    # Keep container alive so docker compose reports it as running
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
