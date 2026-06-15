"""
Unit tests for run_poll_back() in apps/worker/app/main.py.

The poll-back loop's responsibility is to find accepted_candidate
bookings that are no longer available on the portal and mark them
as expired. Tests use mocks for both the API client and the portal
adapter — no real browser, no real DB.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.main import run_poll_back
from app.portal_adapters.fake_ride_portal import PORTAL_NAME

pytestmark = pytest.mark.asyncio


def _candidate(external_id: str, booking_id: str = "u-1", portal: str = PORTAL_NAME) -> dict:
    return {
        "id": booking_id,
        "external_booking_id": external_id,
        "portal_name": portal,
        "status": "accepted_candidate",
    }


class TestPollBackEmptyCases:
    async def test_no_candidates_does_nothing(self):
        """If there are no accepted_candidate bookings, no API call happens."""
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(return_value=[])
        adapter.list_available_jobs = AsyncMock(return_value=["A1", "A2"])

        await run_poll_back(adapter, api)

        # Portal not even consulted if there are no candidates
        adapter.list_available_jobs.assert_not_called()
        api.mark_expired.assert_not_called()

    async def test_portal_list_fails_silently(self):
        """If the portal's list_available_jobs() raises, the loop must
        not crash the worker poll cycle."""
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[_candidate("A1", booking_id="u-1")]
        )
        adapter.list_available_jobs = AsyncMock(
            side_effect=Exception("portal down")
        )

        # Should NOT raise
        await run_poll_back(adapter, api)

        # No booking was expired because the portal list itself failed
        api.mark_expired.assert_not_called()


class TestPollBackExpiredCases:
    async def test_candidate_no_longer_on_portal_marks_expired(self):
        """The booking vanished from the portal → mark_expired is called."""
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[_candidate("GHOST", booking_id="u-ghost")]
        )
        api.mark_expired = AsyncMock(return_value=None)
        api.post_log = AsyncMock(return_value=None)
        adapter.list_available_jobs = AsyncMock(return_value=["OTHER1", "OTHER2"])

        await run_poll_back(adapter, api)

        api.mark_expired.assert_called_once()
        # Verify it was called with the right booking id + a reason
        call = api.mark_expired.call_args
        assert call.args[0] == "u-ghost"
        assert "no longer" in call.args[1].lower() or "taken" in call.args[1].lower()

    async def test_candidate_still_on_portal_left_alone(self):
        """The booking is still on the portal → mark_expired is NOT called."""
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[_candidate("STILL_THERE", booking_id="u-stay")]
        )
        api.mark_expired = AsyncMock(return_value=None)
        api.post_log = AsyncMock(return_value=None)
        adapter.list_available_jobs = AsyncMock(return_value=["STILL_THERE", "OTHER"])

        await run_poll_back(adapter, api)

        api.mark_expired.assert_not_called()

    async def test_mixed_some_expired_some_still_there(self):
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[
                _candidate("GONE1", booking_id="u-1"),
                _candidate("STILL", booking_id="u-2"),
                _candidate("GONE2", booking_id="u-3"),
            ]
        )
        api.mark_expired = AsyncMock(return_value=None)
        api.post_log = AsyncMock(return_value=None)
        adapter.list_available_jobs = AsyncMock(
            return_value=["STILL", "OTHER_NEW"]
        )

        await run_poll_back(adapter, api)

        # Only the two "gone" ones are expired
        assert api.mark_expired.call_count == 2
        expired_ids = {call.args[0] for call in api.mark_expired.call_args_list}
        assert expired_ids == {"u-1", "u-3"}


class TestPollBackPortalFiltering:
    async def test_candidate_from_other_portal_ignored(self):
        """The worker only manages bookings from its own portal."""
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[
                _candidate("OTHER_PORTAL_JOB", booking_id="u-x", portal="some_other_portal"),
            ]
        )
        api.mark_expired = AsyncMock(return_value=None)
        adapter.list_available_jobs = AsyncMock(return_value=[])

        await run_poll_back(adapter, api)

        # Bookings from other portals must not be touched
        api.mark_expired.assert_not_called()

    async def test_own_portal_bookings_are_processed(self):
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[_candidate("MY_PORTAL_JOB", booking_id="u-mine")]
        )
        api.mark_expired = AsyncMock(return_value=None)
        api.post_log = AsyncMock(return_value=None)
        adapter.list_available_jobs = AsyncMock(return_value=[])

        await run_poll_back(adapter, api)

        api.mark_expired.assert_called_once()
        assert api.mark_expired.call_args.args[0] == "u-mine"


class TestPollBackLogging:
    async def test_automation_log_sent_on_expire(self):
        """Each expired booking should also create an automation log entry."""
        adapter = MagicMock()
        api = MagicMock()
        api.list_accepted_candidates = AsyncMock(
            return_value=[_candidate("GHOST", booking_id="u-1")]
        )
        api.mark_expired = AsyncMock(return_value=None)
        api.post_log = AsyncMock(return_value=None)
        adapter.list_available_jobs = AsyncMock(return_value=[])

        await run_poll_back(adapter, api)

        api.post_log.assert_called_once()
        call = api.post_log.call_args
        log_payload = call.kwargs.get("") or call.args[0]
        # Either arg or kwarg
        if not log_payload:
            log_payload = call.args[0]
        assert log_payload["step"] == "poll_back"
        assert log_payload["level"] == "info"
        assert log_payload["external_booking_id"] == "GHOST"
