"""
API tests for /api/logs and /api/portal-status endpoints.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestLogsApi:
    async def test_create_log_returns_201(self, client: AsyncClient):
        resp = await client.post("/api/logs", json={
            "portal_name": "test_portal",
            "level": "info",
            "step": "worker_start",
            "message": "Worker started",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["portal_name"] == "test_portal"
        assert data["step"] == "worker_start"
        assert "id" in data

    async def test_create_log_with_metadata(self, client: AsyncClient):
        resp = await client.post("/api/logs", json={
            "portal_name": "test_portal",
            "level": "error",
            "step": "selector_failure",
            "message": "No selectors found",
            "external_booking_id": "ABC123",
            "screenshot_path": "/artifacts/screenshots/test.png",
            "html_snapshot_path": "/artifacts/html/test.html",
            "metadata": {"selectors": ["[data-testid='x']"]},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["screenshot_path"] == "/artifacts/screenshots/test.png"
        assert data["external_booking_id"] == "ABC123"

    async def test_list_logs_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_log_missing_required_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/logs", json={"level": "info"})
        assert resp.status_code == 422


class TestPortalStatusApi:
    async def test_upsert_portal_status_healthy(self, client: AsyncClient):
        resp = await client.post("/api/portal-status", json={
            "portal_name": "test_portal",
            "status": "healthy",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        assert resp.json()["auto_accept_paused"] is False

    async def test_upsert_portal_status_degraded(self, client: AsyncClient):
        resp = await client.post("/api/portal-status", json={
            "portal_name": "test_portal",
            "status": "degraded",
            "last_error": "Broken selectors",
            "auto_accept_paused": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["auto_accept_paused"] is True
        assert data["last_error"] == "Broken selectors"

    async def test_upsert_is_idempotent(self, client: AsyncClient):
        await client.post("/api/portal-status", json={"portal_name": "portal_x", "status": "healthy"})
        await client.post("/api/portal-status", json={"portal_name": "portal_x", "status": "degraded"})
        resp = await client.get("/api/portal-status/portal_x")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    async def test_get_portal_status_not_found(self, client: AsyncClient):
        resp = await client.get("/api/portal-status/nonexistent_portal_xyz")
        assert resp.status_code == 404
