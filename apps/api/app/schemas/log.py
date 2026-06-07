from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LogCreateRequest(BaseModel):
    portal_name: str = Field(..., max_length=100)
    level: str = Field(default="info", max_length=20)
    step: str = Field(..., max_length=100)
    message: str
    external_booking_id: str | None = None
    screenshot_path: str | None = None
    html_snapshot_path: str | None = None
    metadata: dict[str, Any] | None = None


class LogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    portal_name: str
    level: str
    step: str
    message: str
    external_booking_id: str | None
    screenshot_path: str | None
    html_snapshot_path: str | None
    metadata_: dict[str, Any] | None = None
    created_at: datetime
