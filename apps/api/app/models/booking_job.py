import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.booking_status import BookingStatus


class BookingJob(Base):
    __tablename__ = "booking_jobs"
    __table_args__ = (
        UniqueConstraint("portal_name", "external_booking_id", name="uq_booking_portal_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_booking_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    portal_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    pickup_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    dropoff_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_value: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    vehicle_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pickup_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Decision fields
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=BookingStatus.NEW.value, index=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw extracted payload for debugging
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Screenshot link when available
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<BookingJob id={self.id} external={self.external_booking_id} status={self.status}>"
