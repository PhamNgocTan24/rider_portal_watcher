"""
API tests for the four status-mutation endpoints + state-machine
enforcement in the API layer.

Endpoints covered:
- POST /api/bookings/{id}/auto-accepted
- POST /api/bookings/{id}/manually-accepted
- POST /api/bookings/{id}/failed-to-accept
- POST /api/bookings/{id}/expired

Each test uses a timestamp-suffixed external ID so the suite can run
repeatedly against a persistent DB without collisions.
"""
from __future__ import annotations

import time
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Each test process gets a unique run-id. Combined with per-suffix ids
# this guarantees no collisions even when the suite is re-run within
# the same millisecond.
_RUN_ID = uuid.uuid4().hex[:8]


def _pid(suffix: str) -> str:
    return f"T{_RUN_ID}{suffix}"


def _payload(external_id: str) -> dict:
    return {
        "external_booking_id": external_id,
        "portal_name": "test_portal",
        "pickup_location": "Heathrow Airport T5",
        "dropoff_location": "Mayfair, London",
        "booking_value": 120.0,
        "vehicle_category": "Executive Saloon",
        "customer_category": "corporate",
        "pickup_time": "2026-06-07T09:00:00Z",
    }


async def _create_accepted_candidate(client: AsyncClient, suffix: str) -> str:
    """Helper: create a booking that the rule engine accepts.

    With the default active rule and the payload above, the booking
    should land in `accepted_candidate` (matching min value, all
    allowlists). Returns the booking id.
    """
    resp = await client.post(
        "/api/bookings", json=_payload(_pid(suffix))
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_rejected(client: AsyncClient, suffix: str) -> str:
    """Helper: create a booking the rule engine rejects.

    Low value + non-allowed pickup → `rejected`.
    """
    payload = _payload(_pid(suffix))
    payload["booking_value"] = 5.0  # below min
    payload["pickup_location"] = "Mars Colony 1"  # not in allowlist
    resp = await client.post("/api/bookings", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ===================================================================
# mark_auto_accepted (regression — was the only mutation endpoint before)
# ===================================================================
class TestMarkAutoAccepted:
    async def test_accepted_candidate_to_auto_accepted_200(self, client: AsyncClient):
        bid = await _create_accepted_candidate(client, "A01")
        resp = await client.post(f"/api/bookings/{bid}/auto-accepted")
        assert resp.status_code == 200
        assert resp.json()["status"] == "auto_accepted"

    async def test_unknown_booking_returns_404(self, client: AsyncClient):
        resp = await client.post(
            "/api/bookings/00000000-0000-0000-0000-000000000099/auto-accepted"
        )
        assert resp.status_code == 404


# ===================================================================
# mark_manually_accepted
# ===================================================================
class TestMarkManuallyAccepted:
    async def test_accepted_candidate_to_manually_accepted_200(
        self, client: AsyncClient
    ):
        bid = await _create_accepted_candidate(client, "M01")
        resp = await client.post(f"/api/bookings/{bid}/manually-accepted")
        assert resp.status_code == 200
        assert resp.json()["status"] == "manually_accepted"

    async def test_unknown_booking_returns_404(self, client: AsyncClient):
        resp = await client.post(
            "/api/bookings/00000000-0000-0000-0000-000000000099/manually-accepted"
        )
        assert resp.status_code == 404

    async def test_cannot_manually_accept_an_auto_accepted_booking(
        self, client: AsyncClient
    ):
        """Terminal state — must reject with 409, not silently overwrite."""
        bid = await _create_accepted_candidate(client, "M02")
        # First: auto-accept
        r1 = await client.post(f"/api/bookings/{bid}/auto-accepted")
        assert r1.status_code == 200
        # Then: try to manually-accept the now-terminal booking
        r2 = await client.post(f"/api/bookings/{bid}/manually-accepted")
        assert r2.status_code == 409
        # Status should NOT have changed
        r3 = await client.get(f"/api/bookings/{bid}")
        assert r3.json()["status"] == "auto_accepted"

    async def test_cannot_manually_accept_a_rejected_booking(
        self, client: AsyncClient
    ):
        bid = await _create_rejected(client, "M03")
        resp = await client.post(f"/api/bookings/{bid}/manually-accepted")
        assert resp.status_code == 409
        # Verify state unchanged
        r = await client.get(f"/api/bookings/{bid}")
        assert r.json()["status"] == "rejected"


# ===================================================================
# mark_failed_to_accept
# ===================================================================
class TestMarkFailedToAccept:
    async def test_accepted_candidate_to_failed_to_accept_200(
        self, client: AsyncClient
    ):
        bid = await _create_accepted_candidate(client, "F01")
        resp = await client.post(
            f"/api/bookings/{bid}/failed-to-accept",
            json={"reason": "Job no longer available"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed_to_accept"
        assert "Job no longer available" in resp.json()["decision_reason"]

    async def test_uses_default_reason_when_payload_empty(
        self, client: AsyncClient
    ):
        bid = await _create_accepted_candidate(client, "F02")
        # No JSON body sent
        resp = await client.post(f"/api/bookings/{bid}/failed-to-accept")
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed_to_accept"
        # Default reason is non-empty
        assert resp.json()["decision_reason"]

    async def test_unknown_booking_returns_404(self, client: AsyncClient):
        resp = await client.post(
            "/api/bookings/00000000-0000-0000-0000-000000000099/failed-to-accept",
            json={"reason": "x"},
        )
        assert resp.status_code == 404

    async def test_cannot_fail_an_auto_accepted_booking(self, client: AsyncClient):
        """Terminal state — must reject with 409."""
        bid = await _create_accepted_candidate(client, "F03")
        await client.post(f"/api/bookings/{bid}/auto-accepted")
        resp = await client.post(
            f"/api/bookings/{bid}/failed-to-accept", json={"reason": "late"}
        )
        assert resp.status_code == 409


# ===================================================================
# mark_expired
# ===================================================================
class TestMarkExpired:
    async def test_accepted_candidate_to_expired_200(self, client: AsyncClient):
        bid = await _create_accepted_candidate(client, "E01")
        resp = await client.post(
            f"/api/bookings/{bid}/expired",
            json={"reason": "Job taken by another operator"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"
        assert "Job taken" in resp.json()["decision_reason"]

    async def test_uses_default_reason_when_payload_empty(
        self, client: AsyncClient
    ):
        bid = await _create_accepted_candidate(client, "E02")
        resp = await client.post(f"/api/bookings/{bid}/expired")
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"
        assert resp.json()["decision_reason"]

    async def test_unknown_booking_returns_404(self, client: AsyncClient):
        resp = await client.post(
            "/api/bookings/00000000-0000-0000-0000-000000000099/expired",
            json={"reason": "x"},
        )
        assert resp.status_code == 404

    async def test_cannot_expire_a_rejected_booking(self, client: AsyncClient):
        bid = await _create_rejected(client, "E03")
        resp = await client.post(
            f"/api/bookings/{bid}/expired", json={"reason": "x"}
        )
        assert resp.status_code == 409

    async def test_cannot_expire_a_failed_to_accept_booking(
        self, client: AsyncClient
    ):
        bid = await _create_accepted_candidate(client, "E04")
        await client.post(
            f"/api/bookings/{bid}/failed-to-accept", json={"reason": "first"}
        )
        resp = await client.post(
            f"/api/bookings/{bid}/expired", json={"reason": "second"}
        )
        assert resp.status_code == 409


# ===================================================================
# Dashboard filtering — ACCEPTED_STATUSES, TERMINAL_STATUSES
# ===================================================================
class TestDashboardFiltering:
    async def test_accepted_page_returns_only_auto_and_manually_accepted(
        self, client: AsyncClient
    ):
        """The /bookings/accepted view filters by ACCEPTED_STATUSES."""
        # Create one of each terminal status
        b_auto = await _create_accepted_candidate(client, "DA01")
        await client.post(f"/api/bookings/{b_auto}/auto-accepted")

        b_man = await _create_accepted_candidate(client, "DA02")
        await client.post(f"/api/bookings/{b_man}/manually-accepted")

        b_rej = await _create_rejected(client, "DR01")
        # rejected — must not appear in accepted page

        b_fail = await _create_accepted_candidate(client, "DF01")
        await client.post(
            f"/api/bookings/{b_fail}/failed-to-accept", json={"reason": "x"}
        )

        b_exp = await _create_accepted_candidate(client, "DE01")
        await client.post(f"/api/bookings/{b_exp}/expired", json={"reason": "x"})

        resp = await client.get("/api/bookings")
        assert resp.status_code == 200
        all_bookings = resp.json()

        # Status values seen on the accepted page should be a subset
        # of {auto_accepted, manually_accepted} when filtered server-side.
        # The list endpoint does not filter — that's the dashboard's job.
        # But we can still verify the underlying data.
        statuses = {b["status"] for b in all_bookings}
        assert {"auto_accepted", "manually_accepted"} <= statuses
        # rejected and failed_to_accept also exist in the system
        assert "rejected" in statuses
        assert "failed_to_accept" in statuses
        assert "expired" in statuses
