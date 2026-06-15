"""
HTTP client for communicating with the FastAPI backend.
"""
from __future__ import annotations

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger()


class ApiClient:
    def __init__(self) -> None:
        self._base = settings.api_base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ApiClient":
        self._client = httpx.AsyncClient(base_url=self._base, timeout=30)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None, "ApiClient must be used as async context manager"
        return self._client

    async def post_booking(self, payload: dict) -> dict:
        resp = await self.client.post("/api/bookings", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def post_log(self, payload: dict) -> None:
        try:
            resp = await self.client.post("/api/logs", json=payload)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("api_log_failed", error=str(exc))

    async def post_portal_status(self, payload: dict) -> None:
        try:
            resp = await self.client.post("/api/portal-status", json=payload)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("api_portal_status_failed", error=str(exc))

    async def get_portal_status(self, portal_name: str) -> dict | None:
        try:
            resp = await self.client.get(f"/api/portal-status/{portal_name}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("api_get_portal_status_failed", error=str(exc))
            return None

    async def mark_auto_accepted(self, booking_id: str) -> None:
        try:
            resp = await self.client.post(f"/api/bookings/{booking_id}/auto-accepted")
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("api_mark_auto_accepted_failed", error=str(exc))

    async def set_booking_screenshot(self, booking_id: str, screenshot_path: str) -> None:
        """Attach a screenshot URL to the BookingJob record."""
        try:
            resp = await self.client.patch(
                f"/api/bookings/{booking_id}/screenshot",
                json={"screenshot_path": screenshot_path},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("api_set_booking_screenshot_failed", error=str(exc))

    async def mark_failed_to_accept(self, booking_id: str, reason: str) -> None:
        """Worker calls this when auto-accept click fails."""
        try:
            resp = await self.client.post(
                f"/api/bookings/{booking_id}/failed-to-accept",
                json={"reason": reason},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("api_mark_failed_to_accept_failed", error=str(exc))

    async def mark_expired(self, booking_id: str, reason: str) -> None:
        """Worker calls this when poll-back detects a candidate job is gone."""
        try:
            resp = await self.client.post(
                f"/api/bookings/{booking_id}/expired",
                json={"reason": reason},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("api_mark_expired_failed", error=str(exc))

    async def list_accepted_candidates(self) -> list[dict]:
        """Return all bookings with status=accepted_candidate for poll-back."""
        try:
            resp = await self.client.get(
                "/api/bookings", params={"status": "accepted_candidate"}
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("api_list_accepted_candidates_failed", error=str(exc))
            return []

    async def booking_exists(self, portal_name: str, external_booking_id: str) -> bool:
        """
        Check if a booking already exists in API DB.

        Worker calls this before extracting detail to skip already-processed
        jobs (in case the worker's local seen_ids cache was cleared).

        Returns False on any error — worker must not crash on transient
        API failures, the poll cycle should continue.
        """
        try:
            resp = await self.client.get(
                "/api/bookings/exists",
                params={"portal_name": portal_name, "external_booking_id": external_booking_id},
            )
            resp.raise_for_status()
            return resp.json().get("exists", False)
        except Exception as exc:
            logger.warning("api_booking_exists_failed", error=str(exc))
            return False
