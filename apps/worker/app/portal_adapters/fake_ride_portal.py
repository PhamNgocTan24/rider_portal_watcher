"""
Playwright adapter for the fake ride portal.
Implements login, health check, list jobs, extract detail, accept job.
"""
from __future__ import annotations

import re
import structlog
from playwright.async_api import Browser, BrowserContext, Page

from app.config import settings
from app.portal_adapters import selectors
from app.portal_adapters.base import (
    SelectorNotFoundError,
    find_first_available,
    save_html_snapshot,
    save_screenshot,
)

logger = structlog.get_logger()

PORTAL_NAME = "fake_ride_portal"


class FakeRidePortalAdapter:
    def __init__(self, browser: Browser, api_client: object) -> None:
        self._browser = browser
        self._api = api_client
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def _ensure_page(self) -> Page:
        if self._context is None:
            self._context = await self._browser.new_context()
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
        return self._page

    async def close(self) -> None:
        if self._context:
            await self._context.close()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    async def health_check(self) -> dict:
        """Hit /health and return the JSON payload."""
        import httpx
        url = f"{settings.fake_portal_base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                logger.info("portal_health_check", status=data.get("status"), layout=data.get("layout"))
                return data
        except Exception as exc:
            logger.error("portal_health_check_failed", error=str(exc))
            return {"status": "down", "error": str(exc)}

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    async def login(self) -> None:
        page = await self._ensure_page()
        login_url = f"{settings.fake_portal_base_url}/login"
        logger.info("portal_login", url=login_url)

        await page.goto(login_url, wait_until="domcontentloaded")

        username_sel = await find_first_available(page, selectors.LOGIN_USERNAME_INPUT, context="login")
        password_sel = await find_first_available(page, selectors.LOGIN_PASSWORD_INPUT, context="login")
        submit_sel = await find_first_available(page, selectors.LOGIN_SUBMIT_BUTTON, context="login")

        await page.fill(username_sel, settings.fake_portal_username)
        await page.fill(password_sel, settings.fake_portal_password)
        await page.click(submit_sel)

        # Wait for redirect to /rides
        await page.wait_for_url("**/rides", timeout=10000)
        logger.info("portal_login_success", portal=PORTAL_NAME)

        await self._api.post_log({
            "portal_name": PORTAL_NAME,
            "level": "info",
            "step": "portal_login",
            "message": "Worker logged in to fake ride portal successfully.",
        })

    # ------------------------------------------------------------------
    # List available jobs
    # ------------------------------------------------------------------
    async def list_available_jobs(self) -> list[str]:
        """Return list of external_booking_ids visible on /rides."""
        page = await self._ensure_page()
        rides_url = f"{settings.fake_portal_base_url}/rides"
        await page.goto(rides_url, wait_until="domcontentloaded")

        try:
            card_sel = await find_first_available(
                page, selectors.BOOKING_CARD, timeout_ms=5000, context="list_jobs"
            )
        except SelectorNotFoundError:
            # No rides available — not an error
            logger.info("list_jobs_empty", portal=PORTAL_NAME)
            return []

        cards = await page.query_selector_all(card_sel)
        ids: list[str] = []
        for card in cards:
            # Try data-booking-id attribute first (Layout A)
            bid = await card.get_attribute("data-booking-id")
            if not bid:
                # Layout B: read the .job-id text
                try:
                    id_el = await card.query_selector(".job-id")
                    if id_el:
                        bid = (await id_el.inner_text()).strip()
                except Exception:
                    pass
            if bid:
                ids.append(bid)

        logger.info("list_jobs_found", count=len(ids), portal=PORTAL_NAME)
        return ids

    # ------------------------------------------------------------------
    # Extract job detail
    # ------------------------------------------------------------------
    async def extract_job_detail(self, external_booking_id: str) -> dict:
        """Navigate to detail page and extract all booking fields."""
        page = await self._ensure_page()
        url = f"{settings.fake_portal_base_url}/rides/{external_booking_id}"
        await page.goto(url, wait_until="domcontentloaded")

        async def _text(sel_list: list[str], ctx: str) -> str | None:
            try:
                sel = await find_first_available(page, sel_list, timeout_ms=3000, context=ctx)
                el = await page.query_selector(sel)
                return (await el.inner_text()).strip() if el else None
            except SelectorNotFoundError:
                return None

        pickup   = await _text(selectors.DETAIL_PICKUP,      "pickup")
        dropoff  = await _text(selectors.DETAIL_DROPOFF,     "dropoff")
        value    = await _text(selectors.DETAIL_VALUE,       "value")
        vehicle  = await _text(selectors.DETAIL_VEHICLE,     "vehicle")
        customer = await _text(selectors.DETAIL_CUSTOMER,    "customer")
        pickup_time = await _text(selectors.DETAIL_PICKUP_TIME, "pickup_time")

        # Parse £120.00 -> 120.0
        booking_value: float | None = None
        if value:
            m = re.search(r"[\d.]+", value.replace(",", ""))
            if m:
                booking_value = float(m.group())

        detail = {
            "external_booking_id": external_booking_id,
            "portal_name": PORTAL_NAME,
            "pickup_location": pickup,
            "dropoff_location": dropoff,
            "booking_value": booking_value,
            "vehicle_category": vehicle,
            "customer_category": customer,
            "pickup_time": pickup_time,
            "raw_payload": {
                "extracted_from": url,
                "raw_value_text": value,
            },
        }
        logger.info("job_detail_extracted", external_booking_id=external_booking_id)
        return detail

    # ------------------------------------------------------------------
    # Accept job
    # ------------------------------------------------------------------
    async def accept_job(self, external_booking_id: str) -> None:
        page = await self._ensure_page()
        url = f"{settings.fake_portal_base_url}/rides/{external_booking_id}"
        await page.goto(url, wait_until="domcontentloaded")

        accept_sel = await find_first_available(
            page, selectors.DETAIL_ACCEPT_BUTTON, timeout_ms=5000, context="accept_job"
        )
        await page.click(accept_sel)
        # Wait for redirect back to detail with accepted status
        await page.wait_for_load_state("domcontentloaded")
        logger.info("job_accepted_on_portal", external_booking_id=external_booking_id)
