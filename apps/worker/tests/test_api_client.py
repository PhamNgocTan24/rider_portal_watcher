"""
Unit tests for worker ApiClient.

Coverage:
- booking_exists() — was missing in worker (CRITICAL: main.py:113 calls it
  but the method was never implemented, only orphan code remained at the
  end of the file). Worker would AttributeError on the first poll cycle.
- list_accepted_candidates() — used by poll-back loop to find stale jobs.
- mark_failed_to_accept() / mark_expired() — error must not crash worker.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.api_client import ApiClient

pytestmark = pytest.mark.asyncio


def _mock_response(status_code: int, json_data: list | dict | None = None) -> MagicMock:
    """Build a mock httpx Response with given status + json payload."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


def _client_with_mock_response(resp: MagicMock) -> tuple[ApiClient, AsyncMock]:
    """Create ApiClient whose internal httpx client returns the given response."""
    api = ApiClient()
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=resp)
    mock_http.post = AsyncMock(return_value=resp)
    mock_http.patch = AsyncMock(return_value=resp)
    api._client = mock_http
    return api, mock_http


# ===================================================================
# booking_exists — REGRESSION GUARD
# ===================================================================
class TestBookingExists:
    async def test_returns_true_when_api_says_exists(self):
        """Worker relies on this to skip already-processed bookings."""
        api, _ = _client_with_mock_response(_mock_response(200, {"exists": True}))
        result = await api.booking_exists("fake_ride_portal", "ABC123")
        assert result is True

    async def test_returns_false_when_api_says_not_exists(self):
        api, _ = _client_with_mock_response(_mock_response(200, {"exists": False}))
        result = await api.booking_exists("fake_ride_portal", "ABC999")
        assert result is False

    async def test_returns_false_on_404(self):
        """API returns 404 for non-existent booking — must not crash worker."""
        api, _ = _client_with_mock_response(_mock_response(404))
        result = await api.booking_exists("fake_ride_portal", "NOPE")
        assert result is False

    async def test_returns_false_on_network_error(self):
        """Network error must not crash the worker — log and skip."""
        api = ApiClient()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
        api._client = mock_http
        result = await api.booking_exists("fake_ride_portal", "X")
        assert result is False

    async def test_uses_correct_query_params(self):
        """Must call /api/bookings/exists with portal_name + external_booking_id."""
        api, mock_http = _client_with_mock_response(_mock_response(200, {"exists": False}))
        await api.booking_exists("fake_ride_portal", "TEST001")
        mock_http.get.assert_called_once()
        call_args = mock_http.get.call_args
        assert "/api/bookings/exists" in call_args.args[0]
        assert call_args.kwargs["params"]["portal_name"] == "fake_ride_portal"
        assert call_args.kwargs["params"]["external_booking_id"] == "TEST001"


# ===================================================================
# list_accepted_candidates — poll-back loop
# ===================================================================
class TestListAcceptedCandidates:
    async def test_returns_list_of_dicts(self):
        candidates = [
            {"id": "u1", "external_booking_id": "A1", "status": "accepted_candidate"},
            {"id": "u2", "external_booking_id": "A2", "status": "accepted_candidate"},
        ]
        api, _ = _client_with_mock_response(_mock_response(200, candidates))
        result = await api.list_accepted_candidates()
        assert result == candidates

    async def test_returns_empty_list_on_error(self):
        """If API fails, return [] — poll-back loop should not crash."""
        api = ApiClient()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("down"))
        api._client = mock_http
        result = await api.list_accepted_candidates()
        assert result == []

    async def test_filters_by_status_accepted_candidate(self):
        api, mock_http = _client_with_mock_response(_mock_response(200, []))
        await api.list_accepted_candidates()
        call_args = mock_http.get.call_args
        assert call_args.kwargs["params"]["status"] == "accepted_candidate"


# ===================================================================
# mark_failed_to_accept / mark_expired — swallow API errors
# ===================================================================
class TestStatusMutationEndpoints:
    async def test_mark_failed_to_accept_calls_api(self):
        api, mock_http = _client_with_mock_response(_mock_response(200))
        await api.mark_failed_to_accept("booking-uuid-1", "Portal error")
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert "/api/bookings/booking-uuid-1/failed-to-accept" in call_args.args[0]
        assert call_args.kwargs["json"]["reason"] == "Portal error"

    async def test_mark_expired_calls_api(self):
        api, mock_http = _client_with_mock_response(_mock_response(200))
        await api.mark_expired("booking-uuid-2", "Job taken")
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert "/api/bookings/booking-uuid-2/expired" in call_args.args[0]
        assert call_args.kwargs["json"]["reason"] == "Job taken"

    async def test_mark_failed_to_accept_swallows_api_error(self):
        """API 5xx must not crash worker — log warning and continue."""
        api = ApiClient()
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        api._client = mock_http
        # Should not raise
        await api.mark_failed_to_accept("uuid", "reason")

    async def test_mark_expired_swallows_api_error(self):
        api = ApiClient()
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        api._client = mock_http
        await api.mark_expired("uuid", "reason")
