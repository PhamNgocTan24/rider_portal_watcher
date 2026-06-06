from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_rule import BusinessRule


class RuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_rule(self) -> BusinessRule | None:
        """Return the first active rule, or None."""
        stmt = select(BusinessRule).where(BusinessRule.is_active == True).limit(1)  # noqa: E712
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[BusinessRule]:
        stmt = select(BusinessRule).order_by(BusinessRule.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
