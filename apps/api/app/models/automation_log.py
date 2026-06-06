import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portal_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info", index=True)
    step: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    external_booking_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extra structured context
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<AutomationLog id={self.id} step={self.step!r} level={self.level}>"
