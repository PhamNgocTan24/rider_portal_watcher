"""
API tests for business rules endpoints.

Covers:
- GET /rules (list)
- POST /rules (create)
- POST /rules/{id} (update)
- POST /rules/{id}/toggle-active

TDD: tests written first, implementation follows.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestListRules:
    async def test_list_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/rules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_contains_default_rule(self, client: AsyncClient):
        """The seed migration creates one active default rule."""
        resp = await client.get("/api/rules")
        rules = resp.json()
        assert len(rules) >= 1
        active = [r for r in rules if r["is_active"]]
        assert len(active) >= 1

    async def test_list_rule_has_required_fields(self, client: AsyncClient):
        resp = await client.get("/api/rules")
        rules = resp.json()
        rule = rules[0]
        assert "id" in rule
        assert "name" in rule
        assert "is_active" in rule
        assert "auto_accept" in rule


class TestCreateRule:
    async def test_create_returns_201(self, client: AsyncClient):
        payload = {
            "name": "Test Rule",
            "min_booking_value": 50.0,
            "allowed_pickup_locations": ["Heathrow"],
            "allowed_vehicle_categories": ["Executive Saloon"],
            "allowed_customer_categories": ["corporate"],
            "auto_accept": False,
            "is_active": False,
        }
        resp = await client.post("/api/rules", json=payload)
        assert resp.status_code == 201

    async def test_create_returns_rule_fields(self, client: AsyncClient):
        payload = {
            "name": "Another Rule",
            "min_booking_value": 75.0,
            "auto_accept": True,
            "is_active": False,
        }
        resp = await client.post("/api/rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Another Rule"
        assert data["min_booking_value"] == 75.0
        assert data["auto_accept"] is True
        assert "id" in data

    async def test_create_missing_name_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/rules", json={"min_booking_value": 50.0})
        assert resp.status_code == 422

    async def test_create_with_minimal_fields(self, client: AsyncClient):
        """Only name is required; all other fields are optional."""
        resp = await client.post("/api/rules", json={"name": "Minimal Rule"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Minimal Rule"
        assert data["min_booking_value"] is None
        assert data["allowed_pickup_locations"] is None


class TestUpdateRule:
    async def _create_rule(self, client: AsyncClient, name: str = "Edit Target") -> dict:
        resp = await client.post("/api/rules", json={
            "name": name,
            "min_booking_value": 50.0,
            "auto_accept": False,
            "is_active": False,
        })
        assert resp.status_code == 201
        return resp.json()

    async def test_update_returns_200(self, client: AsyncClient):
        rule = await self._create_rule(client)
        resp = await client.post(f"/api/rules/{rule['id']}", json={
            "name": "Updated Name",
            "min_booking_value": 100.0,
            "auto_accept": True,
        })
        assert resp.status_code == 200

    async def test_update_changes_fields(self, client: AsyncClient):
        rule = await self._create_rule(client, "Pre-update Rule")
        resp = await client.post(f"/api/rules/{rule['id']}", json={
            "name": "Post-update Rule",
            "min_booking_value": 200.0,
            "auto_accept": True,
            "allowed_pickup_locations": ["Gatwick"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Post-update Rule"
        assert data["min_booking_value"] == 200.0
        assert data["auto_accept"] is True
        assert "Gatwick" in data["allowed_pickup_locations"]

    async def test_update_unknown_rule_returns_404(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/api/rules/{fake_id}", json={"name": "x"})
        assert resp.status_code == 404

    async def test_update_invalid_id_returns_400(self, client: AsyncClient):
        resp = await client.post("/api/rules/not-a-uuid", json={"name": "x"})
        assert resp.status_code == 400


class TestToggleRuleActive:
    async def _create_rule(self, client: AsyncClient, active: bool = False) -> dict:
        resp = await client.post("/api/rules", json={
            "name": "Toggle Target",
            "auto_accept": False,
            "is_active": active,
        })
        assert resp.status_code == 201
        return resp.json()

    async def test_toggle_active_to_inactive(self, client: AsyncClient):
        rule = await self._create_rule(client, active=True)
        resp = await client.post(f"/api/rules/{rule['id']}/toggle-active")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_toggle_inactive_to_active(self, client: AsyncClient):
        rule = await self._create_rule(client, active=False)
        resp = await client.post(f"/api/rules/{rule['id']}/toggle-active")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    async def test_toggle_unknown_returns_404(self, client: AsyncClient):
        resp = await client.post(f"/api/rules/{uuid.uuid4()}/toggle-active")
        assert resp.status_code == 404
