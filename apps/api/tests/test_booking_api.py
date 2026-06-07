"""
API-level tests for booking endpoints.
Covers: create, deduplication, list, filter, exists, auto-accepted.

Uses timestamp-suffixed IDs so tests can run repeatedly against a
persistent DB without collisions.
"""
from __future__ import annotations

import time

import pytest
import pytest_asyncio
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Fresh suffix per test run
_TS = str(int(time.time()))[-6:]


def _pid(suffix: str) -> str:
    """Generate a test-run-unique booking ID."""
    return f"T{_TS}{suffix}"


BOOKING_PAYLOAD = {
    "external_booking_id": _pid("BASE"),
    "portal_name": "test_portal",
    "pickup_location": "Heathrow Airport T5",
    "dropoff_location": "Mayfair, London",
    "booking_value": 120.0,
    "vehicle_category": "Executive Saloon",
    "customer_category": "corporate",
    "pickup_time": "2026-06-07T09:00:00Z",
}


class TestCreateBooking:
    async def test_create_returns_201(self, client: AsyncClient):
        resp = await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": _pid("C01")})
        assert resp.status_code == 201

    async def test_create_returns_decision_fields(self, client: AsyncClient):
        resp = await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": _pid("C02")})
        data = resp.json()
        assert "id" in data
        assert data["portal_name"] == "test_portal"
        assert "status" in data
        assert "auto_accept_allowed" in data
        assert data["already_exists"] is False

    async def test_create_missing_required_fields_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/bookings", json={"external_booking_id": "X"})
        assert resp.status_code == 422


class TestDeduplication:
    async def test_duplicate_returns_201_with_already_exists_true(self, client: AsyncClient):
        payload = {**BOOKING_PAYLOAD, "external_booking_id": _pid("D01")}
        r1 = await client.post("/api/bookings", json=payload)
        assert r1.status_code == 201
        assert r1.json()["already_exists"] is False
        r2 = await client.post("/api/bookings", json=payload)
        assert r2.status_code == 201
        assert r2.json()["already_exists"] is True

    async def test_duplicate_has_same_id(self, client: AsyncClient):
        payload = {**BOOKING_PAYLOAD, "external_booking_id": _pid("D02")}
        r1 = await client.post("/api/bookings", json=payload)
        r2 = await client.post("/api/bookings", json=payload)
        assert r1.json()["id"] == r2.json()["id"]

    async def test_same_id_different_portal_creates_two_rows(self, client: AsyncClient):
        eid = _pid("D03")
        r1 = await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": eid, "portal_name": "portal_a"})
        r2 = await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": eid, "portal_name": "portal_b"})
        assert r1.json()["already_exists"] is False
        assert r2.json()["already_exists"] is False
        assert r1.json()["id"] != r2.json()["id"]


class TestListBookings:
    async def test_list_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/bookings")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_filter_by_status(self, client: AsyncClient):
        await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": _pid("L01")})
        resp = await client.get("/api/bookings?status=new")
        assert resp.status_code == 200
        for b in resp.json():
            assert b["status"] == "new"

    async def test_list_filter_rejected_empty_when_none(self, client: AsyncClient):
        resp = await client.get("/api/bookings?status=rejected")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestBookingExists:
    async def test_exists_true(self, client: AsyncClient):
        eid = _pid("E01")
        await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": eid})
        resp = await client.get(f"/api/bookings/exists?portal_name=test_portal&external_booking_id={eid}")
        assert resp.status_code == 200
        assert resp.json()["exists"] is True

    async def test_exists_false(self, client: AsyncClient):
        resp = await client.get("/api/bookings/exists?portal_name=test_portal&external_booking_id=NOPE999XYZ")
        assert resp.status_code == 200
        assert resp.json()["exists"] is False


class TestAutoAccepted:
    async def test_mark_auto_accepted(self, client: AsyncClient):
        r = await client.post("/api/bookings", json={**BOOKING_PAYLOAD, "external_booking_id": _pid("A01")})
        booking_id = r.json()["id"]
        resp = await client.post(f"/api/bookings/{booking_id}/auto-accepted")
        assert resp.status_code == 200
        assert resp.json()["status"] == "auto_accepted"

    async def test_mark_auto_accepted_not_found(self, client: AsyncClient):
        resp = await client.post("/api/bookings/00000000-0000-0000-0000-000000000099/auto-accepted")
        assert resp.status_code == 404
