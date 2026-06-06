import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PortalStatus(Base):
    __tablename__ = "portal_status"
    __table_args__ = (
        UniqueConstraint("portal_name", name="uq_portal_status_portal_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portal_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Status values: healthy | degraded | down
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="healthy")

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_accept_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<PortalStatus portal={self.portal_name!r} status={self.status}>"
