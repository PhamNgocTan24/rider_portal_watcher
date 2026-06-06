import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class BusinessRule(Base):
    __tablename__ = "business_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    min_booking_value: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Allow-lists stored as PostgreSQL text arrays
    allowed_pickup_locations: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    allowed_vehicle_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    allowed_customer_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )

    auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<BusinessRule id={self.id} name={self.name!r} active={self.is_active}>"
