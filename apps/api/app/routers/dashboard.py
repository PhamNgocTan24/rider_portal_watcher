from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.booking_status import BookingStatus, ACCEPTED_STATUSES
from app.models.business_rule import BusinessRule
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
        "new": sum(1 for b in all_bookings if b.status == BookingStatus.ACCEPTED_CANDIDATE.value),
        "accepted": sum(1 for b in all_bookings if b.status in {s.value for s in ACCEPTED_STATUSES}),
        "rejected": sum(1 for b in all_bookings if b.status == BookingStatus.REJECTED.value),
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
    bookings = await repo.list_by_status(BookingStatus.ACCEPTED_CANDIDATE.value)
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "New Bookings", "active": "new",
    })


@router.get("/bookings/accepted", response_class=HTMLResponse)
async def bookings_accepted(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = BookingRepository(db)
    # "Accepted" = auto_accepted + manually_accepted
    bookings = await repo.list_by_statuses([s.value for s in ACCEPTED_STATUSES])
    bookings = list(bookings)
    bookings.sort(key=lambda b: b.detected_at, reverse=True)
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "Accepted Bookings", "active": "accepted",
    })


@router.get("/bookings/rejected", response_class=HTMLResponse)
async def bookings_rejected(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = BookingRepository(db)
    bookings = await repo.list_by_status(BookingStatus.REJECTED.value)
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "Rejected Bookings", "active": "rejected",
    })


@router.get("/bookings/failed", response_class=HTMLResponse)
async def bookings_failed(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = BookingRepository(db)
    bookings = await repo.list_by_statuses([
        BookingStatus.FAILED_TO_ACCEPT.value,
        BookingStatus.EXPIRED.value,
    ])
    bookings = list(bookings)
    bookings.sort(key=lambda b: b.detected_at, reverse=True)
    return templates.TemplateResponse("dashboard/bookings.html", {
        "request": request, "bookings": bookings,
        "title": "Failed / Expired Bookings", "active": "failed",
    })


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    repo = RuleRepository(db)
    rules = await repo.list_all()
    return templates.TemplateResponse("dashboard/rules.html", {
        "request": request, "rules": rules, "active": "rules",
    })


@router.post("/rules", response_class=HTMLResponse)
async def create_rule_form(
    request: Request,
    name: str = Form(...),
    min_booking_value: float | None = Form(default=None),
    allowed_pickup_locations: str = Form(default=""),
    allowed_vehicle_categories: str = Form(default=""),
    allowed_customer_categories: str = Form(default=""),
    auto_accept: str = Form(default="off"),
    is_active: str = Form(default="off"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle rule creation form from dashboard."""
    repo = RuleRepository(db)

    def _parse_list(s: str) -> list[str] | None:
        items = [x.strip() for x in s.split(",") if x.strip()]
        return items if items else None

    rule = BusinessRule(
        name=name,
        min_booking_value=min_booking_value,
        allowed_pickup_locations=_parse_list(allowed_pickup_locations),
        allowed_vehicle_categories=_parse_list(allowed_vehicle_categories),
        allowed_customer_categories=_parse_list(allowed_customer_categories),
        auto_accept=(auto_accept == "on"),
        is_active=(is_active == "on"),
    )
    await repo.create(rule)
    await db.commit()
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/rules/{rule_id}", response_class=HTMLResponse)
async def update_rule_form(
    request: Request,
    rule_id: str,
    name: str = Form(...),
    min_booking_value: float | None = Form(default=None),
    allowed_pickup_locations: str = Form(default=""),
    allowed_vehicle_categories: str = Form(default=""),
    allowed_customer_categories: str = Form(default=""),
    auto_accept: str = Form(default="off"),
    is_active: str = Form(default="off"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle rule update form from dashboard."""
    import uuid as _uuid
    try:
        rid = _uuid.UUID(rule_id)
    except ValueError:
        return RedirectResponse(url="/rules", status_code=303)

    repo = RuleRepository(db)
    rule = await repo.get_by_id(rid)
    if not rule:
        return RedirectResponse(url="/rules", status_code=303)

    def _parse_list(s: str) -> list[str] | None:
        items = [x.strip() for x in s.split(",") if x.strip()]
        return items if items else None

    rule.name = name
    rule.min_booking_value = min_booking_value
    rule.allowed_pickup_locations = _parse_list(allowed_pickup_locations)
    rule.allowed_vehicle_categories = _parse_list(allowed_vehicle_categories)
    rule.allowed_customer_categories = _parse_list(allowed_customer_categories)
    rule.auto_accept = (auto_accept == "on")
    rule.is_active = (is_active == "on")

    await repo.save(rule)
    await db.commit()
    return RedirectResponse(url="/rules", status_code=303)


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
