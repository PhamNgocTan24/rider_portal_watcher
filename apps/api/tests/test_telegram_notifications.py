"""
Tests for Telegram notification coverage.

Strategy: mock the _send() function and verify the right notification
functions are called when bookings are transitioned.

TDD: tests written before wiring the calls.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_BASE_PAYLOAD = {
    "portal_name": "test_portal",
    "pickup_location": "Heathrow Airport T5",
    "dropoff_location": "Mayfair, London",
    "booking_value": 120.0,
    "vehicle_category": "Executive Saloon",
    "customer_category": "corporate",
    "pickup_time": "2026-06-07T09:00:00Z",
}

_RUN = uuid.uuid4().hex[:6]


def _pid(s: str) -> str:
    return f"TG{_RUN}{s}"


async def _create_candidate(client: AsyncClient, suffix: str) -> str:
    """Create a booking that lands in accepted_candidate. Return booking id."""
    resp = await client.post("/api/bookings", json={
        **_BASE_PAYLOAD,
        "external_booking_id": _pid(suffix),
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestAutoAcceptedTelegramNotification:
    async def test_mark_auto_accepted_sends_telegram(self, client: AsyncClient):
        """
        When worker calls POST /api/bookings/{id}/auto-accepted,
        notify_booking_decision should be called with status='auto_accepted'.
        """
        bid = await _create_candidate(client, "AA01")

        with patch(
            "app.services.telegram._send", new_callable=AsyncMock
        ) as mock_send:
            resp = await client.post(f"/api/bookings/{bid}/auto-accepted")
            assert resp.status_code == 200
            assert resp.json()["status"] == "auto_accepted"
            # _send should have been called at least once with "auto_accepted"
            assert mock_send.called
            combined = " ".join(str(c) for c in mock_send.call_args_list)
            assert "auto_accepted" in combined

    async def test_mark_manually_accepted_sends_telegram(self, client: AsyncClient):
        """
        When operator calls POST /api/bookings/{id}/manually-accepted,
        notify_booking_decision should fire with status='manually_accepted'.
        """
        bid = await _create_candidate(client, "MA01")

        with patch(
            "app.services.telegram._send", new_callable=AsyncMock
        ) as mock_send:
            resp = await client.post(f"/api/bookings/{bid}/manually-accepted")
            assert resp.status_code == 200
            assert resp.json()["status"] == "manually_accepted"
            assert mock_send.called
            combined = " ".join(str(c) for c in mock_send.call_args_list)
            assert "manually_accepted" in combined


class TestAutomationErrorTelegramNotification:
    async def test_portal_degraded_via_api_sends_telegram(self, client: AsyncClient):
        """
        POST /api/portal-status with status='degraded' should trigger
        notify_portal_degraded → _send.
        """
        with patch(
            "app.services.telegram._send", new_callable=AsyncMock
        ) as mock_send:
            resp = await client.post("/api/portal-status", json={
                "portal_name": "tg_test_portal",
                "status": "degraded",
                "last_error": "No selectors found",
                "auto_accept_paused": True,
            })
            assert resp.status_code == 200
            assert mock_send.called
            combined = " ".join(str(c) for c in mock_send.call_args_list)
            assert "degraded" in combined.lower() or "Portal degraded" in combined
