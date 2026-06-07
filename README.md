# RidePortal Watcher

A portfolio-grade MVP demonstrating **production-minded browser automation** for a transportation booking portal. Built with Python, Playwright, FastAPI, PostgreSQL, and Docker.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Full System Flow](#full-system-flow)
3. [How to Verify It Works](#how-to-verify-it-works)
4. [Demo Scenarios](#demo-scenarios)
5. [Running Tests](#running-tests)
6. [Architecture](#architecture)
7. [Project Structure](#project-structure)
8. [Environment Variables](#environment-variables)

---

## Quick Start

```bash
git clone git@github.com:PhamNgocTan24/rider_portal_watcher.git
cd rider_portal_watcher
docker compose up --build
```

Wait until all 4 containers are healthy (about 20–30 seconds). Then open:

| Service | URL |
|---|---|
| Fake partner portal | http://localhost:3000 |
| Admin dashboard | http://localhost:8000 |
| Swagger API docs | http://localhost:8000/docs |

Demo credentials: **`demo` / `demo123`**

---

## Full System Flow

This section describes exactly what happens from startup to a booking being evaluated and stored.

### 1. Startup

```
docker compose up --build
        │
        ├─► postgres starts, tables created via Alembic migrations
        ├─► fake-portal starts, seeds 2 demo rides, exposes /health
        ├─► api starts, runs migrations, exposes /health
        └─► worker starts, waits for api + fake-portal /health to return 200
```

The worker will not start polling until both `api` and `fake-portal` are reachable. This is enforced by a retry loop inside `apps/worker/app/main.py`.

---

### 2. Worker Login

```
worker
  └─► Playwright launches Chromium (headless)
  └─► navigates to http://fake-portal:3000/login
  └─► fills username=demo, password=demo123
  └─► clicks Sign In
  └─► waits for redirect to /rides (confirms login success)
  └─► POST /api/logs  ← "portal_login_success"
```

Selectors used at this step (with fallback chain):
```
Username:  [data-testid="input-username"]  →  #username  →  input[name="username"]
Password:  [data-testid="input-password"]  →  #password  →  input[name="password"]
Button:    [data-testid="btn-login"]       →  button[type="submit"]  →  .btn-primary
```

---

### 3. Poll Loop (every 10 seconds by default)

```
worker (every WORKER_POLL_INTERVAL_SECONDS)
  │
  ├─[Step A]─► GET http://fake-portal:3000/health
  │              ├─ status="ok", layout="layout_a"  →  continue
  │              ├─ status="ok", layout="broken"    →  mark portal degraded, skip scraping
  │              └─ status="down"                   →  mark portal down, skip scraping
  │
  ├─[Step B]─► navigate to /rides, extract all booking IDs on the page
  │              ├─ Layout A: reads [data-testid="booking-card"] → data-booking-id attribute
  │              └─ Layout B: reads .job-row → .job-id text (fallback)
  │
  ├─[Step C]─► for each NEW booking ID (not yet seen or in API):
  │              ├─► GET /api/bookings/exists?portal_name=...&external_booking_id=...
  │              │       (skip if already stored)
  │              ├─► navigate to /rides/{id}, extract detail fields
  │              │       pickup, dropoff, value, vehicle, customer, pickup_time
  │              │       (each field has 2–3 fallback selectors for Layout B)
  │              └─► POST /api/bookings  ← extracted payload
  │
  └─[Step D]─► if API returns auto_accept_allowed=true AND status=accepted_candidate:
                 ├─► navigate to /rides/{id}
                 ├─► click [data-testid="btn-accept"] (or fallback .accept-btn)
                 └─► POST /api/bookings/{id}/auto-accepted
```

---

### 4. API Processes the Booking

```
POST /api/bookings
  │
  ├─► Check duplicate: SELECT WHERE portal_name + external_booking_id
  │       └─ if exists → return existing record, already_exists=true (no duplicate row)
  │
  ├─► INSERT INTO booking_jobs (status="new")
  │
  ├─► Load active business rule from business_rules WHERE is_active=true
  │
  ├─► Rule engine evaluates (in order):
  │       1. Portal healthy?          → if not: auto_accept_allowed=false
  │       2. booking_value >= min?    → if not: status=rejected, reason="Booking value below minimum"
  │       3. pickup in allow-list?    → if not: status=rejected, reason="Pickup location is not allowed"
  │       4. vehicle in allow-list?   → if not: status=rejected, reason="Vehicle category is not allowed"
  │       5. customer in allow-list?  → if not: status=rejected, reason="Customer category is not allowed"
  │       6. All passed              → status=accepted_candidate, auto_accept_allowed=rule.auto_accept
  │
  ├─► UPDATE booking_jobs SET status=..., decision_reason=...
  │
  ├─► Telegram notification sent (if TELEGRAM_BOT_TOKEN configured):
  │       - "New booking detected" message
  │       - "Booking decision: accepted_candidate / rejected" message
  │
  └─► Return BookingDecisionResponse to worker
```

---

### 5. Broken Layout Flow

```
fake-portal layout switched to "broken"
  │
  ├─► worker health check: GET /health → layout="broken"
  ├─► worker skips scraping entirely
  ├─► POST /api/portal-status { status="degraded", auto_accept_paused=true }
  ├─► POST /api/logs { level="warning", step="portal_health_check" }
  └─► Telegram alert: "Portal degraded" (if configured)

If scraping was in progress when layout broke:
  ├─► SelectorNotFoundError is raised
  ├─► screenshot saved to /app/artifacts/screenshots/
  ├─► HTML snapshot saved to /app/artifacts/html_snapshots/
  ├─► POST /api/logs with screenshot_path + html_snapshot_path
  └─► POST /api/portal-status { status="degraded", auto_accept_paused=true }

Recovery:
  ├─► layout switched back to layout_a or layout_b
  └─► next poll cycle: health check returns "ok" → scraping resumes normally
```

---

### 6. Dashboard

The FastAPI dashboard reads directly from PostgreSQL and renders Jinja2 templates.

| Page | URL | Shows |
|---|---|---|
| Overview | http://localhost:8000/ | Booking counts, portal status, recent logs |
| New bookings | http://localhost:8000/bookings/new | Bookings with status `new` |
| Accepted | http://localhost:8000/bookings/accepted | `accepted_candidate` + `auto_accepted` |
| Rejected | http://localhost:8000/bookings/rejected | `rejected` with reason |
| Rules | http://localhost:8000/rules | Active business rule config |
| Logs | http://localhost:8000/logs | All automation log entries |
| Portal status | http://localhost:8000/portal-status | Health + auto-accept paused flag |

---

## How to Verify It Works

Step-by-step checklist to confirm the full stack is functioning.

### Step 1 — Confirm all services are healthy

```bash
# All 4 should return {"status":"ok"}
curl http://localhost:8000/health
curl http://localhost:3000/health
```

Expected:
```json
{"status":"ok","service":"api","database":"ok"}
{"status":"ok","service":"fake-portal","layout":"layout_a"}
```

---

### Step 2 — Confirm worker logged in

```bash
docker logs rider_portal_watcher-worker-1 2>&1 | grep -E "worker_start|portal_login"
```

Expected output:
```
worker_start  api_base_url=http://api:8000 ...
portal_login  url=http://fake-portal:3000/login
portal_login_success  portal=fake_ride_portal
```

---

### Step 3 — Publish a job and confirm it was detected

```bash
curl -X POST http://localhost:3000/admin/publish-job \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "pickup=Heathrow+Airport+T5&dropoff=Mayfair&value=120&vehicle=Executive+Saloon&customer_category=corporate&pickup_time=2026-06-07T09:00:00Z&notes="
```

Wait 10–15 seconds, then:

```bash
curl http://localhost:8000/api/bookings | python3 -m json.tool
```

Expected: at least one booking with `"status": "accepted_candidate"` and `"decision_reason": "Matched all active rules"`.

---

### Step 4 — Confirm worker logs show extraction

```bash
docker logs rider_portal_watcher-worker-1 2>&1 | grep -E "list_jobs_found|job_detail_extracted|booking_processed"
```

Expected:
```
list_jobs_found    count=1 portal=fake_ride_portal
job_detail_extracted  external_booking_id=XXXXXXXX
booking_processed  status=accepted_candidate auto_accept_allowed=False
```

---

### Step 5 — Test Layout B fallback

```bash
# Switch to Layout B
curl -X POST http://localhost:3000/admin/switch-layout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "layout=layout_b"

# Publish another job
curl -X POST http://localhost:3000/admin/publish-job \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "pickup=Heathrow+Airport+T5&dropoff=Gatwick&value=90&vehicle=Saloon&customer_category=corporate&pickup_time=2026-06-07T11:00:00Z&notes="
```

After ~15 seconds, check logs:

```bash
docker logs rider_portal_watcher-worker-1 2>&1 | grep "selector_fallback_used"
```

Expected: multiple lines showing `selector_fallback_used` with `fallback_index=1` or higher.

---

### Step 6 — Test broken layout detection

```bash
# Switch to broken layout
curl -X POST http://localhost:3000/admin/switch-layout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "layout=broken"
```

After ~15 seconds:

```bash
# Check portal status is degraded
curl http://localhost:8000/api/portal-status/fake_ride_portal | python3 -m json.tool
```

Expected:
```json
{
  "status": "degraded",
  "auto_accept_paused": true,
  "last_error": "Portal is in broken layout mode"
}
```

Switch back to normal when done:
```bash
curl -X POST http://localhost:3000/admin/switch-layout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "layout=layout_a"
```

---

### Step 7 — Check dashboard pages all load

```bash
for path in "/" "/bookings/new" "/bookings/accepted" "/bookings/rejected" "/rules" "/logs" "/portal-status"; do
  echo -n "$path → "
  python3 -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000$path'); print(r.status)"
done
```

Expected: all return `200`.

---

### Step 8 — Test rejected booking rule

```bash
curl -X POST http://localhost:3000/admin/switch-layout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "layout=layout_a"

# Publish a job that should be rejected (value too low)
curl -X POST http://localhost:3000/admin/publish-job \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "pickup=Zone+6+Romford&dropoff=Luton&value=20&vehicle=MPV&customer_category=leisure&pickup_time=2026-06-07T03:00:00Z&notes="
```

After worker polls:
```bash
curl "http://localhost:8000/api/bookings?status=rejected" | python3 -m json.tool
```

Expected: booking with `"decision_reason": "Booking value below minimum ..."` or `"Pickup location is not allowed"`.

---

## Demo Scenarios

### Scenario A — Full happy path
1. `docker compose up --build`
2. Open http://localhost:3000, log in as `demo/demo123`
3. Admin Controls → Publish Job (defaults)
4. Check http://localhost:8000/bookings/accepted within 15 seconds

### Scenario B — Rejected booking
1. Publish a job with Value=20, Pickup=Zone 6 Romford
2. Check http://localhost:8000/bookings/rejected

### Scenario C — Layout B (fallback selectors)
1. Admin Controls → Switch layout → Layout B
2. Publish a job
3. Check http://localhost:8000/logs for `selector_fallback_used` entries

### Scenario D — Broken portal
1. Admin Controls → Switch layout → Broken
2. Check http://localhost:8000/portal-status — degraded, auto-accept paused
3. Switch back to Layout A — worker recovers on next poll

### Scenario E — Auto-accept enabled
```bash
docker exec rider_portal_watcher-postgres-1 \
  psql -U rideportal -d rideportal \
  -c "UPDATE business_rules SET auto_accept = true WHERE name = 'Default Rule';"
```
Publish a qualifying job → booking status becomes `auto_accepted`.

---

## Running Tests

### Worker tests (no DB required)

```bash
docker compose run --rm worker sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio -q &&
  /app/.venv/bin/pytest tests/ -v"
```

Covers:
- `find_first_available` — first selector matches, fallback to 2nd/3rd, all fail → SelectorNotFoundError
- Portal safety — degraded flag blocks auto-accept, error payload structure

### API tests (requires postgres)

```bash
docker compose up -d postgres api
# wait ~10 seconds for migrations to run, then:

docker compose run --rm \
  -e DATABASE_URL=postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal \
  api sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio httpx -q &&
  /app/.venv/bin/pytest tests/ -v"
```

Covers:
- Rule engine (12 tests) — accepted, rejected, portal degraded, auto-accept flag
- Booking CRUD + deduplication (12 tests) — create, duplicate detection, list, filter, exists, auto-accepted
- Logs API (4 tests) — create with metadata, list
- Portal status API (4 tests) — upsert, idempotent update, not found

### Expected result

```
33 passed (API)
12 passed (worker)
─────────────────
45 passed total
```

---

## Architecture

```
┌─────────────────────────────┐
│     Fake Partner Portal      │  :3000
│  (FastAPI + Jinja2)          │
│  Layout A / B / Broken       │
└──────────────┬──────────────┘
               │  Playwright browser automation
               ▼
┌─────────────────────────────┐        ┌──────────────────┐
│      Playwright Worker       │──HTTP─▶│   FastAPI API    │──▶ PostgreSQL
│  - Login                     │        │   + Dashboard    │    :5432
│  - Poll /rides               │        │                  │
│  - Extract booking detail    │◀───────│  - Deduplicate   │
│  - POST booking to API       │decision│  - Rule engine   │
│  - Click accept (if allowed) │        │  - Store result  │
│  - Screenshot on failure     │        │  - Telegram      │
└─────────────────────────────┘        └──────────────────┘
                                                │
                                         Jinja2 Dashboard
                                         :8000/bookings/*
                                         :8000/rules
                                         :8000/logs
                                         :8000/portal-status
```

### Service startup order

```
postgres ──healthy──▶ api (runs migrations) ──healthy──▶
fake-portal ──healthy──▶ worker (starts polling)
```

### Resilience behaviour

| Situation | What happens |
|---|---|
| Portal layout changes to B | Worker uses fallback selectors automatically, booking processed normally |
| Portal switches to broken | Health check detects it, scraping skipped, portal marked `degraded`, auto-accept paused |
| Selector not found mid-scrape | Screenshot + HTML saved, log sent to API, portal marked `degraded` |
| Single booking extraction fails | Error logged, worker continues to next booking |
| Duplicate booking submitted | API returns `already_exists=true`, no duplicate DB row |
| Login fails | Logged as `critical`, portal marked `down`, worker stops |
| Telegram not configured | Logs `Telegram disabled`, app continues normally |

---

## Project Structure

```
apps/
  api/
    app/
      models/           SQLAlchemy ORM — BookingJob, BusinessRule, AutomationLog, PortalStatus
      schemas/          Pydantic — request/response shapes
      repositories/     DB queries (no raw SQL in routes)
      services/         rule_engine.py, booking_service.py, telegram.py
      routers/          bookings.py, logs.py, portal_status.py, dashboard.py
      templates/        Jinja2 HTML pages
      static/           CSS
    alembic/            Migrations (0001 schema, 0002 seed default rule)
    tests/              pytest — rule engine, booking API, logs API, portal status API
  worker/
    app/
      portal_adapters/
        selectors.py    Centralised fallback selector lists
        base.py         find_first_available(), SelectorNotFoundError, screenshot/html helpers
        fake_ride_portal.py  Full Playwright adapter
      api_client.py     HTTP client for all API calls
      main.py           Poll loop, broken layout handling, auto-accept flow
    tests/              pytest — selector fallback, portal safety
  fake_partner_portal/
    app/
      main.py           Routes: login, rides, accept, publish-job, switch-layout
      state.py          In-memory ride store + layout mode
      templates/        Login, rides list, ride detail (Layout A + B + Broken)
artifacts/
  screenshots/          Auto-saved on failure
  html_snapshots/       Auto-saved on failure
docker-compose.yml
.env.example
```

---

## Environment Variables

Copy `.env.example` to `.env` — defaults work out of the box with Docker Compose.

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal` | Async DB URL |
| `FAKE_PORTAL_BASE_URL` | `http://fake-portal:3000` | Portal base URL (inside Docker) |
| `FAKE_PORTAL_USERNAME` | `demo` | Portal login username |
| `FAKE_PORTAL_PASSWORD` | `demo123` | Portal login password |
| `WORKER_POLL_INTERVAL_SECONDS` | `10` | How often worker polls for new rides |
| `WORKER_HEADLESS` | `true` | Run Chromium headless (set `false` to see the browser) |
| `WORKER_SCREENSHOT_DIR` | `/app/artifacts/screenshots` | Where failure screenshots are saved |
| `WORKER_HTML_SNAPSHOT_DIR` | `/app/artifacts/html_snapshots` | Where HTML snapshots are saved |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Optional — leave empty to disable |
| `TELEGRAM_CHAT_ID` | *(empty)* | Optional — leave empty to disable |

---

## Implementation Status

| Task | Description | Status |
|---|---|---|
| 1 | Project skeleton | ✅ |
| 2 | Database + Alembic migrations | ✅ |
| 3 | Fake partner portal (Layout A/B/Broken) | ✅ |
| 4 | Booking API with deduplication | ✅ |
| 5 | Rule engine | ✅ |
| 6 | Telegram service (optional) | ✅ |
| 7 | Dashboard (7 pages) | ✅ |
| 8 | Worker login | ✅ |
| 9 | Booking monitoring + extraction | ✅ |
| 10 | Auto-accept flow | ✅ |
| 11 | Selector fallback (Layout B) | ✅ |
| 12 | Broken layout + failure evidence | ✅ |
| 13 | Tests (45 passing) | ✅ |
| 14 | Documentation + demo script | ✅ |
| 15 | Final polish | ✅ |
