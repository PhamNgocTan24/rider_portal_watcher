from __future__ import annotations

from typing import Sequence

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.booking_repository import BookingRepository
from app.schemas.booking import (
    BookingCreateRequest,
    BookingDecisionResponse,
    BookingResponse,
)
from app.services.booking_service import BookingService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=BookingDecisionResponse, status_code=201)
async def create_booking(
    req: BookingCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> BookingDecisionResponse:
    """
    Worker submits a newly extracted booking.
    Returns the stored booking with decision status and auto_accept_allowed flag.
    Duplicate submissions (same portal + external_booking_id) return the
    existing record without error — already_exists=True signals the worker.
    """
    service = BookingService(db)
    return await service.create_or_get(req)


@router.post("/{booking_id}/auto-accepted", response_model=BookingResponse)
async def mark_auto_accepted(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """Worker calls this after it successfully clicks accept on the portal."""
    service = BookingService(db)
    booking = await service.mark_auto_accepted(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse.model_validate(booking)


@router.post("/{booking_id}/manually-accepted", response_model=BookingResponse)
async def mark_manually_accepted(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """Operator confirms acceptance from the dashboard."""
    service = BookingService(db)
    try:
        booking = await service.mark_manually_accepted(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse.model_validate(booking)


@router.post("/{booking_id}/failed-to-accept", response_model=BookingResponse)
async def mark_failed_to_accept(
    booking_id: str,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """Worker calls this when auto-accept click fails (job taken by competitor, portal error)."""
    service = BookingService(db)
    reason = payload.get("reason", "Auto-accept failed on portal") if payload else "Auto-accept failed on portal"
    try:
        booking = await service.mark_failed_to_accept(booking_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse.model_validate(booking)


@router.post("/{booking_id}/expired", response_model=BookingResponse)
async def mark_expired(
    booking_id: str,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """Worker calls this when poll-back detects the job is no longer available on the portal."""
    service = BookingService(db)
    reason = payload.get("reason", "Job no longer available on portal") if payload else "Job no longer available on portal"
    try:
        booking = await service.mark_expired(booking_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse.model_validate(booking)


@router.patch("/{booking_id}/screenshot", response_model=BookingResponse)
async def set_screenshot(
    booking_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """Worker calls this to attach a screenshot URL to a booking record."""
    import uuid
    try:
        bid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")

    repo = BookingRepository(db)
    booking = await repo.get_by_id(bid)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.screenshot_path = payload.get("screenshot_path")
    await db.commit()
    await db.refresh(booking)
    return BookingResponse.model_validate(booking)


@router.get("", response_model=list[BookingResponse])
async def list_bookings(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Sequence[BookingResponse]:
    """
    List bookings, optionally filtered by status.
    Valid status values: new | accepted_candidate | auto_accepted |
                         manually_accepted | failed_to_accept | rejected | expired
    """
    repo = BookingRepository(db)
    bookings = await repo.list_by_status(status)
    return [BookingResponse.model_validate(b) for b in bookings]


@router.get("/exists")
async def booking_exists(
    portal_name: str,
    external_booking_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Worker uses this to check if a booking was already processed."""
    repo = BookingRepository(db)
    exists = await repo.exists(portal_name, external_booking_id)
    return {"exists": exists}


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    import uuid

    try:
        bid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")

    repo = BookingRepository(db)
    booking = await repo.get_by_id(bid)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse.model_validate(booking)
