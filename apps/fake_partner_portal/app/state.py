"""
In-memory state for the fake partner portal.
Intentionally simple — this is a demo target, not a real service.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
LayoutMode = Literal["layout_a", "layout_b", "broken"]

# ---------------------------------------------------------------------------
# Demo credentials
# ---------------------------------------------------------------------------
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"

# ---------------------------------------------------------------------------
# Layout state (mutable, shared across requests)
# ---------------------------------------------------------------------------
current_layout: LayoutMode = "layout_a"

# ---------------------------------------------------------------------------
# Ride store: dict[external_booking_id, ride_dict]
# ---------------------------------------------------------------------------
rides: dict[str, dict] = {}


def _make_ride(
    pickup: str,
    dropoff: str,
    value: float,
    vehicle: str,
    customer_category: str,
    pickup_time: str,
    status: str = "available",
    notes: str = "",
) -> dict:
    return {
        "external_booking_id": str(uuid.uuid4())[:8].upper(),
        "pickup_location": pickup,
        "dropoff_location": dropoff,
        "booking_value": value,
        "vehicle_category": vehicle,
        "customer_category": customer_category,
        "pickup_time": pickup_time,
        "status": status,  # available | accepted
        "notes": notes,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def seed_rides() -> None:
    """Populate with two demo rides (accepted scenario + rejected scenario)."""
    if rides:
        return  # already seeded

    accepted = _make_ride(
        pickup="Heathrow Airport T5",
        dropoff="Mayfair, London",
        value=120.00,
        vehicle="Executive Saloon",
        customer_category="corporate",
        pickup_time="2026-06-07T09:00:00Z",
        notes="Meet & Greet at arrivals.",
    )
    rejected = _make_ride(
        pickup="Zone 6, Romford",
        dropoff="Luton Airport",
        value=35.00,
        vehicle="MPV",
        customer_category="leisure",
        pickup_time="2026-06-07T03:30:00Z",
        notes="Early morning run.",
    )
    rides[accepted["external_booking_id"]] = accepted
    rides[rejected["external_booking_id"]] = rejected
