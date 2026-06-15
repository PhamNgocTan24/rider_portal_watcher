from __future__ import annotations

import uuid

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

    async def get_by_id(self, rule_id: uuid.UUID) -> BusinessRule | None:
        return await self._session.get(BusinessRule, rule_id)

    async def list_all(self) -> list[BusinessRule]:
        stmt = select(BusinessRule).order_by(BusinessRule.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, rule: BusinessRule) -> BusinessRule:
        self._session.add(rule)
        await self._session.flush()
        await self._session.refresh(rule)
        return rule

    async def save(self, rule: BusinessRule) -> BusinessRule:
        """Persist changes to an existing rule."""
        await self._session.flush()
        await self._session.refresh(rule)
        return rule
