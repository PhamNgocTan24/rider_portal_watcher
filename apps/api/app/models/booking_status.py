"""
BookingStatus enum — single source of truth for all booking status values.

Transition graph:
  new ──────────────────┬──► accepted_candidate ──┬──► auto_accepted
                        │                          ├──► manually_accepted
                        │                          ├──► failed_to_accept
                        │                          └──► expired
                        └──► rejected

Rules:
- new is the entry point (set on creation before rule evaluation)
- accepted_candidate means rules passed, awaiting action
- rejected is a terminal state (rule-engine decision)
- auto_accepted is terminal (worker clicked accept successfully)
- manually_accepted is terminal (operator confirmed via dashboard)
- failed_to_accept is terminal (worker tried to click but job was gone/error)
- expired is terminal (job was available but taken by someone else / timed out)
"""
from __future__ import annotations

from enum import Enum


class BookingStatus(str, Enum):
    NEW                = "new"
    ACCEPTED_CANDIDATE = "accepted_candidate"
    AUTO_ACCEPTED      = "auto_accepted"
    MANUALLY_ACCEPTED  = "manually_accepted"
    FAILED_TO_ACCEPT   = "failed_to_accept"
    REJECTED           = "rejected"
    EXPIRED            = "expired"


# ---------------------------------------------------------------------------
# Valid transitions: from_status → set of allowed to_statuses
# ---------------------------------------------------------------------------
_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.NEW: {
        BookingStatus.ACCEPTED_CANDIDATE,
        BookingStatus.REJECTED,
    },
    BookingStatus.ACCEPTED_CANDIDATE: {
        BookingStatus.AUTO_ACCEPTED,
        BookingStatus.MANUALLY_ACCEPTED,
        BookingStatus.FAILED_TO_ACCEPT,
        BookingStatus.EXPIRED,
    },
    # Terminal states — no outgoing transitions
    BookingStatus.AUTO_ACCEPTED:     set(),
    BookingStatus.MANUALLY_ACCEPTED: set(),
    BookingStatus.FAILED_TO_ACCEPT:  set(),
    BookingStatus.REJECTED:          set(),
    BookingStatus.EXPIRED:           set(),
}


def is_valid_status_transition(
    from_status: BookingStatus | str,
    to_status: BookingStatus | str,
) -> bool:
    """
    Return True if transitioning from_status → to_status is allowed.

    Accepts both enum members and raw strings for convenience.

    Examples:
        is_valid_status_transition("new", "accepted_candidate")  # True
        is_valid_status_transition("rejected", "auto_accepted")  # False
        is_valid_status_transition("auto_accepted", "expired")   # False
    """
    try:
        from_s = BookingStatus(from_status)
        to_s   = BookingStatus(to_status)
    except ValueError:
        return False
    return to_s in _TRANSITIONS.get(from_s, set())


# Convenience sets for dashboard filtering
TERMINAL_STATUSES: frozenset[BookingStatus] = frozenset({
    BookingStatus.AUTO_ACCEPTED,
    BookingStatus.MANUALLY_ACCEPTED,
    BookingStatus.FAILED_TO_ACCEPT,
    BookingStatus.REJECTED,
    BookingStatus.EXPIRED,
})

ACCEPTED_STATUSES: frozenset[BookingStatus] = frozenset({
    BookingStatus.AUTO_ACCEPTED,
    BookingStatus.MANUALLY_ACCEPTED,
})
