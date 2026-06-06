from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PortalStatusUpsertRequest(BaseModel):
    portal_name: str = Field(..., max_length=100)
    status: str = Field(..., max_length=50)  # healthy | degraded | down
    last_error: str | None = None
    auto_accept_paused: bool = False


class PortalStatusResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    portal_name: str
    status: str
    last_checked_at: datetime | None
    last_error: str | None
    auto_accept_paused: bool
    updated_at: datetime
