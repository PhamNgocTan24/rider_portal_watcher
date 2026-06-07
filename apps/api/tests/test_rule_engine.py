"""
Unit tests for the rule engine — no DB, no network.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.booking_job import BookingJob
from app.models.business_rule import BusinessRule
from app.services.rule_engine import RuleDecision, evaluate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booking(**kwargs) -> BookingJob:
    defaults = dict(
        external_booking_id="TEST001",
        portal_name="fake_ride_portal",
        pickup_location="Heathrow Airport T5",
        dropoff_location="Mayfair, London",
        booking_value=Decimal("120.00"),
        vehicle_category="Executive Saloon",
        customer_category="corporate",
        status="new",
    )
    defaults.update(kwargs)
    b = BookingJob()
    for k, v in defaults.items():
        setattr(b, k, v)
    return b


def _rule(**kwargs) -> BusinessRule:
    defaults = dict(
        name="Test Rule",
        min_booking_value=Decimal("50.00"),
        allowed_pickup_locations=["Heathrow", "Gatwick", "Mayfair"],
        allowed_vehicle_categories=["Executive Saloon", "Saloon", "MPV"],
        allowed_customer_categories=["corporate", "vip"],
        auto_accept=False,
        is_active=True,
    )
    defaults.update(kwargs)
    r = BusinessRule()
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRuleEngineAccept:
    def test_all_criteria_met_returns_accepted_candidate(self):
        decision = evaluate(_booking(), _rule())
        assert decision.status == "accepted_candidate"
        assert decision.reason == "Matched all active rules"

    def test_auto_accept_disabled_by_default(self):
        decision = evaluate(_booking(), _rule(auto_accept=False))
        assert decision.auto_accept_allowed is False

    def test_auto_accept_enabled_when_rule_flag_true(self):
        decision = evaluate(_booking(), _rule(auto_accept=True))
        assert decision.status == "accepted_candidate"
        assert decision.auto_accept_allowed is True

    def test_no_active_rule_returns_accepted_candidate_no_auto_accept(self):
        decision = evaluate(_booking(), rule=None)
        assert decision.status == "accepted_candidate"
        assert decision.auto_accept_allowed is False
        assert "No active rule" in decision.reason

    def test_empty_allow_lists_do_not_restrict(self):
        rule = _rule(
            allowed_pickup_locations=[],
            allowed_vehicle_categories=[],
            allowed_customer_categories=[],
        )
        decision = evaluate(_booking(), rule)
        assert decision.status == "accepted_candidate"


class TestRuleEngineReject:
    def test_booking_value_below_minimum_rejected(self):
        b = _booking(booking_value=Decimal("30.00"))
        decision = evaluate(b, _rule(min_booking_value=Decimal("50.00")))
        assert decision.status == "rejected"
        assert "Booking value below minimum" in decision.reason
        assert decision.auto_accept_allowed is False

    def test_booking_value_exactly_minimum_accepted(self):
        b = _booking(booking_value=Decimal("50.00"))
        decision = evaluate(b, _rule(min_booking_value=Decimal("50.00")))
        assert decision.status == "accepted_candidate"

    def test_pickup_location_not_allowed_rejected(self):
        b = _booking(pickup_location="Zone 6, Romford")
        decision = evaluate(b, _rule())
        assert decision.status == "rejected"
        assert "Pickup location is not allowed" in decision.reason

    def test_vehicle_category_not_allowed_rejected(self):
        b = _booking(vehicle_category="Motorbike")
        decision = evaluate(b, _rule())
        assert decision.status == "rejected"
        assert "Vehicle category is not allowed" in decision.reason

    def test_customer_category_not_allowed_rejected(self):
        b = _booking(customer_category="leisure")
        decision = evaluate(b, _rule())
        assert decision.status == "rejected"
        assert "Customer category is not allowed" in decision.reason


class TestPortalSafety:
    def test_degraded_portal_disables_auto_accept(self):
        rule = _rule(auto_accept=True)
        decision = evaluate(_booking(), rule, portal_is_healthy=False)
        assert decision.auto_accept_allowed is False
        assert "Portal degraded" in decision.reason

    def test_degraded_portal_still_returns_accepted_candidate_status(self):
        """Degraded portal doesn't hard-reject — it just pauses auto-accept."""
        rule = _rule(auto_accept=True)
        decision = evaluate(_booking(), rule, portal_is_healthy=False)
        assert decision.status == "accepted_candidate"
