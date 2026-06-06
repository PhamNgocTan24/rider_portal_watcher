"""
Rule engine — deterministic, no external calls, no AI.

Evaluation order (per ARCHITECTURE.md §7):
1. Portal health safety check
2. Minimum booking value
3. Pickup location allow-list
4. Vehicle category allow-list
5. Customer category allow-list
6. Auto-accept flag

Returns a RuleDecision dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.booking_job import BookingJob
from app.models.business_rule import BusinessRule


@dataclass
class RuleDecision:
    status: str          # accepted_candidate | rejected | failed
    reason: str          # human-readable
    auto_accept_allowed: bool


def evaluate(
    booking: BookingJob,
    rule: BusinessRule | None,
    portal_is_healthy: bool = True,
) -> RuleDecision:
    """
    Evaluate a booking against an active business rule.

    If no active rule exists, the booking becomes an accepted_candidate
    with a note that no rules are configured (safe default — operator
    must still review).
    """
    # ------------------------------------------------------------------
    # 1. Portal health safety check
    # ------------------------------------------------------------------
    if not portal_is_healthy:
        return RuleDecision(
            status="accepted_candidate",
            reason="Portal degraded; auto-accept paused",
            auto_accept_allowed=False,
        )

    # ------------------------------------------------------------------
    # No active rule — pass through but disable auto-accept
    # ------------------------------------------------------------------
    if rule is None:
        return RuleDecision(
            status="accepted_candidate",
            reason="No active rule configured; manual review required",
            auto_accept_allowed=False,
        )

    booking_value = float(booking.booking_value or 0)

    # ------------------------------------------------------------------
    # 2. Minimum booking value
    # ------------------------------------------------------------------
    if rule.min_booking_value is not None:
        min_val = float(rule.min_booking_value)
        if booking_value < min_val:
            return RuleDecision(
                status="rejected",
                reason=f"Booking value below minimum (£{booking_value:.2f} < £{min_val:.2f})",
                auto_accept_allowed=False,
            )

    # ------------------------------------------------------------------
    # 3. Pickup location allow-list
    # ------------------------------------------------------------------
    if rule.allowed_pickup_locations:
        pickup = (booking.pickup_location or "").strip().lower()
        allowed = [loc.strip().lower() for loc in rule.allowed_pickup_locations]
        if not any(pickup.startswith(a) or a in pickup for a in allowed):
            return RuleDecision(
                status="rejected",
                reason=f"Pickup location is not allowed: '{booking.pickup_location}'",
                auto_accept_allowed=False,
            )

    # ------------------------------------------------------------------
    # 4. Vehicle category allow-list
    # ------------------------------------------------------------------
    if rule.allowed_vehicle_categories:
        vehicle = (booking.vehicle_category or "").strip().lower()
        allowed = [v.strip().lower() for v in rule.allowed_vehicle_categories]
        if vehicle not in allowed:
            return RuleDecision(
                status="rejected",
                reason=f"Vehicle category is not allowed: '{booking.vehicle_category}'",
                auto_accept_allowed=False,
            )

    # ------------------------------------------------------------------
    # 5. Customer category allow-list
    # ------------------------------------------------------------------
    if rule.allowed_customer_categories:
        customer = (booking.customer_category or "").strip().lower()
        allowed = [c.strip().lower() for c in rule.allowed_customer_categories]
        if customer not in allowed:
            return RuleDecision(
                status="rejected",
                reason=f"Customer category is not allowed: '{booking.customer_category}'",
                auto_accept_allowed=False,
            )

    # ------------------------------------------------------------------
    # 6. All checks passed — auto-accept depends on rule flag
    # ------------------------------------------------------------------
    return RuleDecision(
        status="accepted_candidate",
        reason="Matched all active rules",
        auto_accept_allowed=rule.auto_accept,
    )
