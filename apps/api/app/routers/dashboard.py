from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.booking_repository import BookingRepository
from app.repositories.log_repository import LogRepository
from app.repositories.portal_status_repository import PortalStatusRepository
from app.repositories.rule_repository import RuleRepository

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="/app/app/templates")


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    booking_repo = BookingRepository(db)
    all_bookings = await booking_repo.list_by_status()
    counts = {
        "new": sum(1 for b in all_bookings if b.status == "accepted_candidate"),
        "accepted": sum(1 for b in all_bookings if b.status == "auto_accepted"),
        "rejected": sum(1 for b in all_bookings if b.status == "rejected"),
        "total": len(all_bookings),
    }
    portal_repo = PortalStatusRepository(db)
    portals = await portal_repo.list_all()
    log_repo = LogRepository(db)
    recent_logs = await log_repo.list_recent(limit=5)
    return templates.TemplateResponse("dashboard/overview.html", {
        "request": request, "counts": counts,
        "portals": portals, "recent_logs": recent_logs,
        "active": "overview",
    })


@router.get("/bookings/new", response_class=HTMLResponse)
async def bookings_new(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = BookingRepository(db)
    # "New" bookings = accepted_candidate (awaiting operator review or auto-accept)
    # Status "new" only exists for milliseconds before rule evaluation,
    # so we show accepted_candidate here — these are actionable items.
    bookings = await repo.list_by_status("accepted_candidate")
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "New Bookings", "active": "new",
    })


@router.get("/bookings/accepted", response_class=HTMLResponse)
async def bookings_accepted(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = BookingRepository(db)
    # "Accepted" = auto_accepted (worker confirmed click on portal)
    bookings = await repo.list_by_status("auto_accepted")
    bookings = list(bookings)
    bookings.sort(key=lambda b: b.detected_at, reverse=True)
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "Accepted Bookings", "active": "accepted",
    })


@router.get("/bookings/rejected", response_class=HTMLResponse)
async def bookings_rejected(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = BookingRepository(db)
    bookings = await repo.list_by_status("rejected")
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "Rejected Bookings", "active": "rejected",
    })


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = RuleRepository(db)
    rules = await repo.list_all()
    return templates.TemplateResponse("dashboard/rules.html", {
        "request": request, "rules": rules, "active": "rules",
    })


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = LogRepository(db)
    logs = await repo.list_recent(limit=200)
    return templates.TemplateResponse("dashboard/logs.html", {
        "request": request, "logs": logs, "active": "logs",
    })


@router.get("/portal-status", response_class=HTMLResponse)
async def portal_status_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = PortalStatusRepository(db)
    portals = await repo.list_all()
    return templates.TemplateResponse("dashboard/portal_status.html", {
        "request": request, "portals": portals, "active": "portals",
    })
