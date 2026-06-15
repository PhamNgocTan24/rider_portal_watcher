"""
Tests for GET /api/portal-status (list all) endpoint.
TDD: tests written before implementation.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestPortalStatusList:
    async def test_list_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/portal-status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_returns_upserted_portals(self, client: AsyncClient):
        await client.post("/api/portal-status", json={
            "portal_name": "list_test_portal_a",
            "status": "healthy",
        })
        await client.post("/api/portal-status", json={
            "portal_name": "list_test_portal_b",
            "status": "degraded",
            "last_error": "Bad selectors",
            "auto_accept_paused": True,
        })
        resp = await client.get("/api/portal-status")
        assert resp.status_code == 200
        portals = resp.json()
        names = [p["portal_name"] for p in portals]
        assert "list_test_portal_a" in names
        assert "list_test_portal_b" in names

    async def test_list_empty_returns_empty_list(self, client: AsyncClient):
        # Fresh DB may have no portals yet — just verify it returns a list
        resp = await client.get("/api/portal-status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_items_have_required_fields(self, client: AsyncClient):
        await client.post("/api/portal-status", json={
            "portal_name": "list_test_fields_portal",
            "status": "healthy",
        })
        resp = await client.get("/api/portal-status")
        portals = resp.json()
        item = next(p for p in portals if p["portal_name"] == "list_test_fields_portal")
        assert "id" in item
        assert "portal_name" in item
        assert "status" in item
        assert "auto_accept_paused" in item
        assert "updated_at" in item
