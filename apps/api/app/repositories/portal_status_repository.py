from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal_status import PortalStatus


class PortalStatusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_portal_name(self, portal_name: str) -> PortalStatus | None:
        stmt = select(PortalStatus).where(PortalStatus.portal_name == portal_name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        portal_name: str,
        status: str,
        last_error: str | None = None,
        auto_accept_paused: bool = False,
    ) -> PortalStatus:
        existing = await self.get_by_portal_name(portal_name)
        now = datetime.now(timezone.utc)
        if existing:
            existing.status = status
            existing.last_error = last_error
            existing.auto_accept_paused = auto_accept_paused
            existing.last_checked_at = now
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        ps = PortalStatus(
            portal_name=portal_name,
            status=status,
            last_error=last_error,
            auto_accept_paused=auto_accept_paused,
            last_checked_at=now,
        )
        self._session.add(ps)
        await self._session.flush()
        await self._session.refresh(ps)
        return ps

    async def list_all(self) -> list[PortalStatus]:
        stmt = select(PortalStatus).order_by(PortalStatus.portal_name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
