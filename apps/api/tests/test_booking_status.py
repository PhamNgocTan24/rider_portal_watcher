"""
Unit tests for the BookingStatus enum and state machine.

Pure unit tests — no DB, no network, no async. Tests the contract
defined in apps/api/app/models/booking_status.py.
"""
from __future__ import annotations

import pytest

from app.models.booking_status import (
    ACCEPTED_STATUSES,
    BookingStatus,
    TERMINAL_STATUSES,
    is_valid_status_transition,
)


# ===================================================================
# BookingStatus enum — values must match docs and DB seed data
# ===================================================================
class TestEnumValues:
    def test_all_seven_statuses_exist(self):
        """Regression guard: the enum must have exactly 7 values."""
        values = {s.value for s in BookingStatus}
        assert values == {
            "new",
            "accepted_candidate",
            "auto_accepted",
            "manually_accepted",
            "failed_to_accept",
            "rejected",
            "expired",
        }

    def test_each_member_is_a_str(self):
        """BookingStatus(str, Enum) — must behave like a string."""
        for member in BookingStatus:
            assert isinstance(member.value, str)
            assert isinstance(member, str)


# ===================================================================
# is_valid_status_transition — valid moves
# ===================================================================
class TestValidTransitions:
    def test_new_to_accepted_candidate_valid(self):
        assert is_valid_status_transition("new", "accepted_candidate") is True

    def test_new_to_rejected_valid(self):
        assert is_valid_status_transition("new", "rejected") is True

    def test_accepted_candidate_to_auto_accepted_valid(self):
        assert is_valid_status_transition("accepted_candidate", "auto_accepted") is True

    def test_accepted_candidate_to_manually_accepted_valid(self):
        assert (
            is_valid_status_transition("accepted_candidate", "manually_accepted")
            is True
        )

    def test_accepted_candidate_to_failed_to_accept_valid(self):
        assert (
            is_valid_status_transition("accepted_candidate", "failed_to_accept")
            is True
        )

    def test_accepted_candidate_to_expired_valid(self):
        assert is_valid_status_transition("accepted_candidate", "expired") is True

    def test_enum_members_accepted_as_arguments(self):
        """Helper must accept both raw strings and enum members."""
        assert (
            is_valid_status_transition(
                BookingStatus.NEW, BookingStatus.ACCEPTED_CANDIDATE
            )
            is True
        )


# ===================================================================
# is_valid_status_transition — invalid moves
# ===================================================================
class TestInvalidTransitions:
    def test_new_cannot_skip_to_auto_accepted(self):
        """Must go through accepted_candidate first."""
        assert is_valid_status_transition("new", "auto_accepted") is False

    def test_new_cannot_skip_to_manually_accepted(self):
        assert is_valid_status_transition("new", "manually_accepted") is False

    def test_new_cannot_skip_to_expired(self):
        assert is_valid_status_transition("new", "expired") is False

    def test_new_cannot_skip_to_failed_to_accept(self):
        assert is_valid_status_transition("new", "failed_to_accept") is False

    def test_accepted_candidate_cannot_revert_to_new(self):
        assert is_valid_status_transition("accepted_candidate", "new") is False

    def test_accepted_candidate_cannot_skip_to_rejected(self):
        """Rule evaluation already happened; can't reject after accepting."""
        assert is_valid_status_transition("accepted_candidate", "rejected") is False

    def test_auto_accepted_is_terminal(self):
        for target in (
            "new",
            "accepted_candidate",
            "manually_accepted",
            "failed_to_accept",
            "rejected",
            "expired",
        ):
            assert is_valid_status_transition("auto_accepted", target) is False

    def test_manually_accepted_is_terminal(self):
        for target in (
            "new",
            "accepted_candidate",
            "auto_accepted",
            "failed_to_accept",
            "rejected",
            "expired",
        ):
            assert is_valid_status_transition("manually_accepted", target) is False

    def test_failed_to_accept_is_terminal(self):
        for target in (
            "new",
            "accepted_candidate",
            "auto_accepted",
            "manually_accepted",
            "rejected",
            "expired",
        ):
            assert is_valid_status_transition("failed_to_accept", target) is False

    def test_rejected_is_terminal(self):
        for target in (
            "new",
            "accepted_candidate",
            "auto_accepted",
            "manually_accepted",
            "failed_to_accept",
            "expired",
        ):
            assert is_valid_status_transition("rejected", target) is False

    def test_expired_is_terminal(self):
        for target in (
            "new",
            "accepted_candidate",
            "auto_accepted",
            "manually_accepted",
            "failed_to_accept",
            "rejected",
        ):
            assert is_valid_status_transition("expired", target) is False

    def test_unknown_from_status_returns_false(self):
        assert is_valid_status_transition("nonsense", "new") is False

    def test_unknown_to_status_returns_false(self):
        assert is_valid_status_transition("new", "nonsense") is False

    def test_both_unknown_returns_false(self):
        assert is_valid_status_transition("foo", "bar") is False

    def test_empty_string_returns_false(self):
        assert is_valid_status_transition("", "new") is False
        assert is_valid_status_transition("new", "") is False


# ===================================================================
# ACCEPTED_STATUSES convenience set
# ===================================================================
class TestAcceptedStatusesSet:
    def test_contains_only_auto_and_manually_accepted(self):
        assert ACCEPTED_STATUSES == frozenset(
            {BookingStatus.AUTO_ACCEPTED, BookingStatus.MANUALLY_ACCEPTED}
        )

    def test_does_not_contain_accepted_candidate(self):
        """ACCEPTED_STATUSES is the terminal 'accepted' set, not the candidate set."""
        assert BookingStatus.ACCEPTED_CANDIDATE not in ACCEPTED_STATUSES

    def test_does_not_contain_failed_or_rejected(self):
        for s in (
            BookingStatus.FAILED_TO_ACCEPT,
            BookingStatus.REJECTED,
            BookingStatus.EXPIRED,
            BookingStatus.NEW,
        ):
            assert s not in ACCEPTED_STATUSES


# ===================================================================
# TERMINAL_STATUSES convenience set
# ===================================================================
class TestTerminalStatusesSet:
    def test_contains_all_five_terminal_states(self):
        assert TERMINAL_STATUSES == frozenset(
            {
                BookingStatus.AUTO_ACCEPTED,
                BookingStatus.MANUALLY_ACCEPTED,
                BookingStatus.FAILED_TO_ACCEPT,
                BookingStatus.REJECTED,
                BookingStatus.EXPIRED,
            }
        )

    def test_does_not_contain_new(self):
        assert BookingStatus.NEW not in TERMINAL_STATUSES

    def test_does_not_contain_accepted_candidate(self):
        assert BookingStatus.ACCEPTED_CANDIDATE not in TERMINAL_STATUSES

    def test_count_is_five(self):
        """If this changes, update both the docs and the dashboard logic."""
        assert len(TERMINAL_STATUSES) == 5


# ===================================================================
# is_valid_status_transition — defensive behaviour
# ===================================================================
class TestDefensiveBehaviour:
    def test_none_from_status_does_not_crash(self):
        """The helper must not raise on bad input — it returns False."""
        assert is_valid_status_transition(None, "new") is False

    def test_none_to_status_does_not_crash(self):
        assert is_valid_status_transition("new", None) is False
