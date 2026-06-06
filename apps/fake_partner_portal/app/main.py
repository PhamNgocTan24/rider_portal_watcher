import uuid
from datetime import datetime, timezone

import structlog
from fastapi import Cookie, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import state
from app.state import DEMO_PASSWORD, DEMO_USERNAME, LayoutMode, rides

logger = structlog.get_logger()

app = FastAPI(
    title="RidePortal Fake Partner Portal",
    description="Controlled fake portal for Playwright automation demos.",
    version="0.1.0",
)

templates = Jinja2Templates(directory="/app/app/templates")
app.mount("/static", StaticFiles(directory="/app/app/static"), name="static")

# ---------------------------------------------------------------------------
# Session store: token -> username  (simple in-memory, demo only)
# ---------------------------------------------------------------------------
sessions: dict[str, str] = {}

SESSION_COOKIE = "portal_session"


def get_current_user(portal_session: str | None = Cookie(default=None)) -> str | None:
    if portal_session and portal_session in sessions:
        return sessions[portal_session]
    return None


def require_login(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or token not in sessions:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return sessions[token]


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    state.seed_rides()
    logger.info("fake_portal_started", layout=state.current_layout, rides=len(rides))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", response_class=JSONResponse, tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "fake-portal", "layout": state.current_layout}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse, tags=["auth"])
async def login_page(request: Request, error: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error, "layout": state.current_layout}
    )


@app.post("/login", tags=["auth"])
async def login(
    response: Response,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    if username == DEMO_USERNAME and password == DEMO_PASSWORD:
        token = str(uuid.uuid4())
        sessions[token] = username
        resp = RedirectResponse(url="/rides", status_code=302)
        resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
        logger.info("portal_login_success", username=username)
        return resp
    logger.warning("portal_login_failed", username=username)
    return RedirectResponse(url="/login?error=Invalid+credentials", status_code=302)


@app.get("/logout", tags=["auth"])
async def logout(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sessions.pop(token, None)
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ---------------------------------------------------------------------------
# Rides list
# ---------------------------------------------------------------------------
@app.get("/rides", response_class=HTMLResponse, tags=["rides"])
async def rides_list(request: Request) -> HTMLResponse:
    require_login(request)
    return templates.TemplateResponse(
        "rides.html",
        {
            "request": request,
            "rides": list(rides.values()),
            "layout": state.current_layout,
        },
    )


# ---------------------------------------------------------------------------
# Ride detail
# ---------------------------------------------------------------------------
@app.get("/rides/{external_booking_id}", response_class=HTMLResponse, tags=["rides"])
async def ride_detail(request: Request, external_booking_id: str) -> HTMLResponse:
    require_login(request)
    ride = rides.get(external_booking_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return templates.TemplateResponse(
        "ride_detail.html",
        {
            "request": request,
            "ride": ride,
            "layout": state.current_layout,
        },
    )


# ---------------------------------------------------------------------------
# Accept ride
# ---------------------------------------------------------------------------
@app.post("/rides/{external_booking_id}/accept", tags=["rides"])
async def accept_ride(request: Request, external_booking_id: str) -> Response:
    require_login(request)
    ride = rides.get(external_booking_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    ride["status"] = "accepted"
    logger.info("ride_accepted", external_booking_id=external_booking_id)
    return RedirectResponse(url=f"/rides/{external_booking_id}", status_code=302)


# ---------------------------------------------------------------------------
# Admin: publish job
# ---------------------------------------------------------------------------
@app.post("/admin/publish-job", tags=["admin"])
async def publish_job(
    pickup: str = Form(default="Heathrow Airport T5"),
    dropoff: str = Form(default="Mayfair, London"),
    value: float = Form(default=120.0),
    vehicle: str = Form(default="Executive Saloon"),
    customer_category: str = Form(default="corporate"),
    pickup_time: str = Form(default="2026-06-07T09:00:00Z"),
    notes: str = Form(default=""),
) -> JSONResponse:
    ride = {
        "external_booking_id": str(uuid.uuid4())[:8].upper(),
        "pickup_location": pickup,
        "dropoff_location": dropoff,
        "booking_value": value,
        "vehicle_category": vehicle,
        "customer_category": customer_category,
        "pickup_time": pickup_time,
        "status": "available",
        "notes": notes,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    rides[ride["external_booking_id"]] = ride
    logger.info("job_published", external_booking_id=ride["external_booking_id"])
    return JSONResponse({"ok": True, "external_booking_id": ride["external_booking_id"]})


# ---------------------------------------------------------------------------
# Admin: switch layout
# ---------------------------------------------------------------------------
@app.post("/admin/switch-layout", tags=["admin"])
async def switch_layout(layout: LayoutMode = Form(...)) -> JSONResponse:
    state.current_layout = layout
    logger.info("layout_switched", layout=layout)
    return JSONResponse({"ok": True, "layout": layout})
