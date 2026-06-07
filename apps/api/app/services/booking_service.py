from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking_job import BookingJob
from app.repositories.booking_repository import BookingRepository
from app.repositories.rule_repository import RuleRepository
from app.schemas.booking import BookingCreateRequest, BookingDecisionResponse
from app.services import rule_engine, telegram

logger = structlog.get_logger()


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BookingRepository(session)
        self._rule_repo = RuleRepository(session)

    async def create_or_get(
        self, req: BookingCreateRequest
    ) -> BookingDecisionResponse:
        """
        Deduplicate → persist → evaluate rule → return decision.
        """
        existing = await self._repo.get_by_portal_and_external_id(
            req.portal_name, req.external_booking_id
        )
        if existing:
            logger.info(
                "booking_duplicate_skipped",
                portal_name=req.portal_name,
                external_booking_id=req.external_booking_id,
            )
            return BookingDecisionResponse(
                id=existing.id,
                external_booking_id=existing.external_booking_id,
                portal_name=existing.portal_name,
                status=existing.status,
                decision_reason=existing.decision_reason,
                auto_accept_allowed=False,
                already_exists=True,
            )

        # ------------------------------------------------------------------
        # Persist with status "new" first
        # ------------------------------------------------------------------
        booking = BookingJob(
            external_booking_id=req.external_booking_id,
            portal_name=req.portal_name,
            pickup_location=req.pickup_location,
            dropoff_location=req.dropoff_location,
            booking_value=req.booking_value,
            vehicle_category=req.vehicle_category,
            customer_category=req.customer_category,
            pickup_time=req.pickup_time,
            raw_payload=req.raw_payload,
            status="new",
        )
        booking = await self._repo.create(booking)

        # ------------------------------------------------------------------
        # Evaluate active rule
        # ------------------------------------------------------------------
        active_rule = await self._rule_repo.get_active_rule()
        decision = rule_engine.evaluate(booking, active_rule, portal_is_healthy=True)

        booking = await self._repo.update_status(
            booking, decision.status, decision.reason
        )
        await self._session.commit()

        logger.info(
            "booking_evaluated",
            id=str(booking.id),
            external_booking_id=booking.external_booking_id,
            status=decision.status,
            reason=decision.reason,
            auto_accept_allowed=decision.auto_accept_allowed,
        )

        # Telegram notifications (fire-and-forget, non-blocking)
        await telegram.notify_new_booking(
            external_booking_id=booking.external_booking_id,
            portal_name=booking.portal_name,
            pickup=booking.pickup_location,
            dropoff=booking.dropoff_location,
            value=float(booking.booking_value) if booking.booking_value else None,
        )
        await telegram.notify_booking_decision(
            external_booking_id=booking.external_booking_id,
            status=decision.status,
            reason=decision.reason,
        )

        return BookingDecisionResponse(
            id=booking.id,
            external_booking_id=booking.external_booking_id,
            portal_name=booking.portal_name,
            status=booking.status,
            decision_reason=booking.decision_reason,
            auto_accept_allowed=decision.auto_accept_allowed,
            already_exists=False,
        )

    async def mark_auto_accepted(self, booking_id: str) -> BookingJob | None:
        import uuid as _uuid
        try:
            bid = _uuid.UUID(booking_id)
        except ValueError:
            return None

        booking = await self._repo.get_by_id(bid)
        if not booking:
            return None

        booking = await self._repo.update_status(
            booking, "auto_accepted", "Worker confirmed accept click on portal"
        )
        await self._session.commit()
        logger.info("booking_auto_accepted", id=str(booking.id))
        return booking
