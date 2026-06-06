from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation_log import AutomationLog


class LogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: AutomationLog) -> AutomationLog:
        self._session.add(log)
        await self._session.flush()
        await self._session.refresh(log)
        return log

    async def list_recent(self, limit: int = 100) -> list[AutomationLog]:
        stmt = (
            select(AutomationLog)
            .order_by(AutomationLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
