from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking_job import BookingJob


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, booking_id: uuid.UUID) -> BookingJob | None:
        result = await self._session.get(BookingJob, booking_id)
        return result

    async def get_by_portal_and_external_id(
        self, portal_name: str, external_booking_id: str
    ) -> BookingJob | None:
        stmt = select(BookingJob).where(
            BookingJob.portal_name == portal_name,
            BookingJob.external_booking_id == external_booking_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_status(self, status: str | None = None) -> Sequence[BookingJob]:
        stmt = select(BookingJob).order_by(BookingJob.detected_at.desc())
        if status:
            stmt = stmt.where(BookingJob.status == status)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, booking: BookingJob) -> BookingJob:
        self._session.add(booking)
        await self._session.flush()
        await self._session.refresh(booking)
        return booking

    async def update_status(
        self,
        booking: BookingJob,
        status: str,
        decision_reason: str | None = None,
    ) -> BookingJob:
        booking.status = status
        if decision_reason is not None:
            booking.decision_reason = decision_reason
        await self._session.flush()
        await self._session.refresh(booking)
        return booking

    async def exists(self, portal_name: str, external_booking_id: str) -> bool:
        row = await self.get_by_portal_and_external_id(portal_name, external_booking_id)
        return row is not None
