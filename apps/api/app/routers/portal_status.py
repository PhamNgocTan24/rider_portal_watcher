from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.portal_status_repository import PortalStatusRepository
from app.schemas.portal_status import PortalStatusResponse, PortalStatusUpsertRequest
from app.services import telegram

logger = structlog.get_logger()
router = APIRouter(prefix="/api/portal-status", tags=["portal-status"])


@router.get("", response_model=list[PortalStatusResponse])
async def list_portal_statuses(
    db: AsyncSession = Depends(get_db),
) -> list[PortalStatusResponse]:
    """List health status for all known portals."""
    repo = PortalStatusRepository(db)
    portals = await repo.list_all()
    return [PortalStatusResponse.model_validate(p) for p in portals]


@router.post("", response_model=PortalStatusResponse)
async def upsert_portal_status(
    req: PortalStatusUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> PortalStatusResponse:
    repo = PortalStatusRepository(db)
    ps = await repo.upsert(
        portal_name=req.portal_name,
        status=req.status,
        last_error=req.last_error,
        auto_accept_paused=req.auto_accept_paused,
    )
    await db.commit()

    if req.status == "degraded":
        await telegram.notify_portal_degraded(req.portal_name, req.last_error or "Unknown error")

    logger.info("portal_status_updated", portal=req.portal_name, status=req.status)
    return PortalStatusResponse.model_validate(ps)


@router.get("/{portal_name}", response_model=PortalStatusResponse)
async def get_portal_status(
    portal_name: str,
    db: AsyncSession = Depends(get_db),
) -> PortalStatusResponse:
    repo = PortalStatusRepository(db)
    ps = await repo.get_by_portal_name(portal_name)
    if not ps:
        raise HTTPException(status_code=404, detail="Portal status not found")
    return PortalStatusResponse.model_validate(ps)
