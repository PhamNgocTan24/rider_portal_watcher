from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inbound — worker sends this when it extracts a booking
# ---------------------------------------------------------------------------
class BookingCreateRequest(BaseModel):
    external_booking_id: str = Field(..., max_length=255)
    portal_name: str = Field(..., max_length=100)

    pickup_location: str | None = None
    dropoff_location: str | None = None
    booking_value: float | None = None
    vehicle_category: str | None = None
    customer_category: str | None = None
    pickup_time: datetime | None = None

    raw_payload: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Outbound — what the API returns to the worker / dashboard
# ---------------------------------------------------------------------------
class BookingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    external_booking_id: str
    portal_name: str

    pickup_location: str | None
    dropoff_location: str | None
    booking_value: float | None
    vehicle_category: str | None
    customer_category: str | None
    pickup_time: datetime | None

    status: str
    decision_reason: str | None
    screenshot_path: str | None

    detected_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Worker decision payload — returned after booking is stored + evaluated
# ---------------------------------------------------------------------------
class BookingDecisionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    external_booking_id: str
    portal_name: str
    status: str
    decision_reason: str | None
    auto_accept_allowed: bool = False
    already_exists: bool = False
