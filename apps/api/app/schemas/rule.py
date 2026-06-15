"""
Pydantic schemas for business rule API.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    min_booking_value: float | None = None
    allowed_pickup_locations: list[str] | None = None
    allowed_vehicle_categories: list[str] | None = None
    allowed_customer_categories: list[str] | None = None
    auto_accept: bool = False
    is_active: bool = True


class RuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    min_booking_value: float | None = None
    allowed_pickup_locations: list[str] | None = None
    allowed_vehicle_categories: list[str] | None = None
    allowed_customer_categories: list[str] | None = None
    auto_accept: bool | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    min_booking_value: float | None
    allowed_pickup_locations: list[str] | None
    allowed_vehicle_categories: list[str] | None
    allowed_customer_categories: list[str] | None
    auto_accept: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
