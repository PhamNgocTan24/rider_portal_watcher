from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.automation_log import AutomationLog
from app.repositories.log_repository import LogRepository
from app.schemas.log import LogCreateRequest, LogResponse
from app.services import telegram

logger = structlog.get_logger()
router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.post("", response_model=LogResponse, status_code=201)
async def create_log(
    req: LogCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> LogResponse:
    repo = LogRepository(db)
    log = AutomationLog(
        portal_name=req.portal_name,
        level=req.level,
        step=req.step,
        message=req.message,
        external_booking_id=req.external_booking_id,
        screenshot_path=req.screenshot_path,
        html_snapshot_path=req.html_snapshot_path,
        metadata_=req.metadata,
    )
    log = await repo.create(log)
    await db.commit()

    # Send Telegram alert for critical automation errors
    if req.level in ("error", "critical"):
        logger.warning("automation_log_error", step=req.step, portal=req.portal_name, msg=req.message[:100])
        await telegram.notify_automation_error(
            portal_name=req.portal_name,
            step=req.step,
            message=req.message,
            external_booking_id=req.external_booking_id,
        )

    return LogResponse.model_validate(log)


@router.get("", response_model=list[LogResponse])
async def list_logs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[LogResponse]:
    repo = LogRepository(db)
    logs = await repo.list_recent(limit=limit)
    return [LogResponse.model_validate(log_entry) for log_entry in logs]
