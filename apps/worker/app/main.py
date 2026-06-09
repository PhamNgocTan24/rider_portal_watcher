"""
Playwright worker entry point.

Flow:
1. Wait for API and fake portal to be reachable.
2. Launch Playwright browser.
3. Login to fake portal.
4. Poll loop every WORKER_POLL_INTERVAL_SECONDS:
   a. Health check portal.
   b. List available jobs.
   c. For each new job: extract detail → POST to API → optionally accept.
5. On critical failure: screenshot + HTML snapshot + log + mark portal degraded.
"""
from __future__ import annotations

import asyncio
import traceback

import httpx
import structlog
from playwright.async_api import async_playwright

from app.api_client import ApiClient
from app.config import settings
from app.portal_adapters.base import SelectorNotFoundError, save_html_snapshot, save_screenshot
from app.portal_adapters.fake_ride_portal import PORTAL_NAME, FakeRidePortalAdapter

logger = structlog.get_logger()

# How long to wait between polls after a critical failure (seconds)
ERROR_COOLDOWN_SECONDS = 30


async def wait_for_service(url: str, name: str, retries: int = 30, delay: float = 3.0) -> None:
    """Block until the given URL returns HTTP 200."""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    logger.info(f"{name}_reachable", url=url)
                    return
        except Exception:
            pass
        logger.info(f"waiting_for_{name}", attempt=attempt + 1, url=url)
        await asyncio.sleep(delay)
    raise RuntimeError(f"Service {name} never became reachable at {url}")


async def run_poll_cycle(adapter: FakeRidePortalAdapter, api: ApiClient, seen_ids: set[str]) -> None:
    """One poll cycle: health check → list jobs → process new ones."""

    # 1. Health check
    health = await adapter.health_check()
    portal_status = health.get("status", "down")
    layout = health.get("layout", "unknown")

    if portal_status != "ok":
        await api.post_portal_status({
            "portal_name": PORTAL_NAME,
            "status": "down",
            "last_error": f"Health check returned: {portal_status}",
            "auto_accept_paused": True,
        })
        logger.warning("portal_down", status=portal_status)
        return

    if layout == "broken":
        await api.post_portal_status({
            "portal_name": PORTAL_NAME,
            "status": "degraded",
            "last_error": "Portal is in broken layout mode",
            "auto_accept_paused": True,
        })
        await api.post_log({
            "portal_name": PORTAL_NAME,
            "level": "warning",
            "step": "portal_health_check",
            "message": "Portal is in broken layout mode. Auto-accept paused.",
        })
        logger.warning("portal_layout_broken")
        return

    # Mark healthy
    await api.post_portal_status({
        "portal_name": PORTAL_NAME,
        "status": "healthy",
        "auto_accept_paused": False,
    })

    # 2. List jobs
    job_ids = await adapter.list_available_jobs()

    new_ids = [jid for jid in job_ids if jid not in seen_ids]
    if not new_ids:
        logger.info("poll_no_new_jobs")
        return

    # Log to API that new jobs were found
    await api.post_log({
        "portal_name": PORTAL_NAME,
        "level": "info",
        "step": "list_jobs",
        "message": f"Found {len(new_ids)} new job(s) to process: {', '.join(new_ids)}",
        "metadata": {"new_ids": new_ids, "total_visible": len(job_ids)},
    })

    # 3. Process each new job
    for external_id in new_ids:
        seen_ids.add(external_id)

        # Check if already in API DB
        already_exists = await api.booking_exists(PORTAL_NAME, external_id)
        if already_exists:
            logger.info("booking_already_in_api", external_booking_id=external_id)
            continue

        # Extract detail
        try:
            detail = await adapter.extract_job_detail(external_id)
        except SelectorNotFoundError as exc:
            await _handle_selector_failure(adapter, api, external_id, exc)
            continue
        except Exception as exc:
            await _handle_generic_failure(adapter, api, external_id, "extract_job_detail", exc)
            continue

        # Log successful extraction
        await api.post_log({
            "portal_name": PORTAL_NAME,
            "level": "info",
            "step": "extract_job_detail",
            "external_booking_id": external_id,
            "message": (
                f"Extracted booking: {detail.get('pickup_location')} → {detail.get('dropoff_location')}, "
                f"£{detail.get('booking_value')}, {detail.get('vehicle_category')}, {detail.get('customer_category')}"
            ),
            "metadata": {
                "pickup": detail.get("pickup_location"),
                "dropoff": detail.get("dropoff_location"),
                "value": detail.get("booking_value"),
                "vehicle": detail.get("vehicle_category"),
                "customer": detail.get("customer_category"),
            },
        })

        # POST to API → get decision
        try:
            decision = await api.post_booking(detail)
        except Exception as exc:
            logger.error("post_booking_failed", external_booking_id=external_id, error=str(exc))
            await api.post_log({
                "portal_name": PORTAL_NAME,
                "level": "error",
                "step": "post_booking",
                "external_booking_id": external_id,
                "message": f"Failed to POST booking: {exc}",
            })
            continue

        status = decision.get("status")
        reason = decision.get("decision_reason")
        auto_accept = decision.get("auto_accept_allowed", False)

        logger.info(
            "booking_processed",
            external_booking_id=external_id,
            status=status,
            auto_accept_allowed=auto_accept,
        )

        # For rejected bookings: capture screenshot of the portal as evidence
        rejection_screenshot_path: str | None = None
        if status == "rejected":
            page = adapter._page
            if page and not page.is_closed():
                rejection_screenshot_path = await save_screenshot(
                    page, "rejected", settings.worker_screenshot_dir
                )
                # Also update the BookingJob record so it's visible in the bookings dashboard
                booking_id = decision.get("id")
                if booking_id and rejection_screenshot_path:
                    await api.set_booking_screenshot(booking_id, rejection_screenshot_path)

        # Log rule evaluation result to API
        await api.post_log({
            "portal_name": PORTAL_NAME,
            "level": "info",
            "step": "rule_evaluation",
            "external_booking_id": external_id,
            "message": f"Decision: {status} — {reason}",
            "screenshot_path": rejection_screenshot_path,
            "metadata": {
                "status": status,
                "decision_reason": reason,
                "auto_accept_allowed": auto_accept,
                "already_exists": decision.get("already_exists", False),
            },
        })

        # Auto-accept if API says so
        if auto_accept and status == "accepted_candidate":
            await _try_auto_accept(adapter, api, external_id, decision.get("id"))


async def run_poll_back(adapter: FakeRidePortalAdapter, api: ApiClient) -> None:
    """
    Poll-back: check all accepted_candidate bookings against the portal.
    If a job is no longer listed on the portal, it was taken by someone else → mark expired.
    Runs every poll cycle alongside run_poll_cycle.
    """
    candidates = await api.list_accepted_candidates()
    if not candidates:
        return

    # Get current live job IDs from portal
    try:
        live_ids = set(await adapter.list_available_jobs())
    except Exception as exc:
        logger.warning("poll_back_list_failed", error=str(exc))
        return

    for booking in candidates:
        external_id = booking.get("external_booking_id")
        booking_id  = booking.get("id")
        portal_name = booking.get("portal_name")

        # Only check jobs from this worker's portal
        if portal_name != PORTAL_NAME:
            continue

        if external_id not in live_ids:
            logger.info(
                "poll_back_job_gone",
                external_booking_id=external_id,
                reason="No longer listed on portal",
            )
            await api.mark_expired(
                booking_id,
                "Job no longer available on portal — likely taken by another operator",
            )
            await api.post_log({
                "portal_name": PORTAL_NAME,
                "level": "info",
                "step": "poll_back",
                "external_booking_id": external_id,
                "message": "Job expired: no longer listed on portal.",
            })


async def _try_auto_accept(
    adapter: FakeRidePortalAdapter,
    api: ApiClient,
    external_id: str,
    booking_id: str | None,
) -> None:
    """Click accept on portal then report back to API."""
    try:
        await adapter.accept_job(external_id)
        if booking_id:
            await api.mark_auto_accepted(booking_id)
        await api.post_log({
            "portal_name": PORTAL_NAME,
            "level": "info",
            "step": "auto_accept",
            "external_booking_id": external_id,
            "message": "Job auto-accepted on portal.",
        })
        logger.info("auto_accept_success", external_booking_id=external_id)
    except Exception as exc:
        # Accept failed — job may have been taken by competitor or portal error
        reason = f"Auto-accept failed: {type(exc).__name__}: {exc}"
        if booking_id:
            await api.mark_failed_to_accept(booking_id, reason)
        await _handle_generic_failure(adapter, api, external_id, "auto_accept", exc)


async def _handle_selector_failure(
    adapter: FakeRidePortalAdapter,
    api: ApiClient,
    external_id: str,
    exc: SelectorNotFoundError,
) -> None:
    page = adapter._page
    screenshot_path = None
    html_path = None

    if page and not page.is_closed():
        screenshot_path = await save_screenshot(page, "selector_failure", settings.worker_screenshot_dir)
        html_path = await save_html_snapshot(page, "selector_failure", settings.worker_html_snapshot_dir)

    await api.post_log({
        "portal_name": PORTAL_NAME,
        "level": "error",
        "step": "selector_failure",
        "external_booking_id": external_id,
        "message": str(exc),
        "screenshot_path": screenshot_path,
        "html_snapshot_path": html_path,
        "metadata": {"selectors": exc.selectors, "context": exc.context},
    })
    await api.post_portal_status({
        "portal_name": PORTAL_NAME,
        "status": "degraded",
        "last_error": str(exc),
        "auto_accept_paused": True,
    })
    logger.error("selector_failure", external_booking_id=external_id, error=str(exc))


async def _handle_generic_failure(
    adapter: FakeRidePortalAdapter,
    api: ApiClient,
    external_id: str,
    step: str,
    exc: Exception,
) -> None:
    page = adapter._page
    screenshot_path = None
    html_path = None

    if page and not page.is_closed():
        screenshot_path = await save_screenshot(page, step, settings.worker_screenshot_dir)
        html_path = await save_html_snapshot(page, step, settings.worker_html_snapshot_dir)

    await api.post_log({
        "portal_name": PORTAL_NAME,
        "level": "error",
        "step": step,
        "external_booking_id": external_id,
        "message": f"{type(exc).__name__}: {exc}",
        "screenshot_path": screenshot_path,
        "html_snapshot_path": html_path,
    })
    logger.error(step, external_booking_id=external_id, error=str(exc))


async def main() -> None:
    logger.info(
        "worker_start",
        api_base_url=settings.api_base_url,
        fake_portal_base_url=settings.fake_portal_base_url,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        headless=settings.worker_headless,
    )

    # Wait for dependencies
    await wait_for_service(f"{settings.api_base_url}/health", "api")
    await wait_for_service(f"{settings.fake_portal_base_url}/health", "fake_portal")

    seen_ids: set[str] = set()

    async with ApiClient() as api:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.worker_headless)
            adapter = FakeRidePortalAdapter(browser, api)

            # Login
            try:
                await adapter.login()
            except Exception as exc:
                logger.error("worker_login_failed", error=str(exc), traceback=traceback.format_exc())
                await api.post_log({
                    "portal_name": PORTAL_NAME,
                    "level": "critical",
                    "step": "portal_login",
                    "message": f"Login failed: {exc}",
                })
                await api.post_portal_status({
                    "portal_name": PORTAL_NAME,
                    "status": "down",
                    "last_error": f"Login failed: {exc}",
                    "auto_accept_paused": True,
                })
                raise

            # Poll loop
            while True:
                try:
                    await run_poll_cycle(adapter, api, seen_ids)
                    await run_poll_back(adapter, api)
                except Exception as exc:
                    logger.error(
                        "poll_cycle_error",
                        error=str(exc),
                        traceback=traceback.format_exc(),
                    )
                    await api.post_log({
                        "portal_name": PORTAL_NAME,
                        "level": "error",
                        "step": "poll_cycle",
                        "message": f"Poll cycle error: {exc}",
                    })
                    # Cool down before retrying — do not crash permanently
                    await asyncio.sleep(ERROR_COOLDOWN_SECONDS)
                    continue

                await asyncio.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
