# RidePortal Watcher

A portfolio-grade MVP demonstrating **production-minded browser automation** for a transportation booking portal. Built with Python 3.11, Playwright, FastAPI, PostgreSQL, and Docker Compose.

The system logs into a partner portal, monitors new ride requests, extracts booking details, evaluates configurable business rules, posts results to a FastAPI backend, optionally auto-accepts jobs, sends Telegram notifications, and powers a Jinja2 admin dashboard.

The whole stack runs end-to-end on a developer laptop in under 30 seconds with a single `docker compose up`.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [How to handle environment variables](#how-to-handle-environment-variables)
5. [How to install / update dependencies](#how-to-install--update-dependencies)
6. [Running tests](#running-tests)
7. [Full system flow](#full-system-flow)
8. [How to verify it works](#how-to-verify-it-works)
9. [Demo scenarios](#demo-scenarios)
10. [Architecture](#architecture)
11. [Project structure](#project-structure)
12. [Environment variables reference](#environment-variables-reference)
13. [Troubleshooting](#troubleshooting)

---

## What it does

```
Fake Partner Portal  ← Playwright browser automation
        │ (Chromium headless)
        ▼
Playwright Worker  ←─ HTTP ─►  FastAPI API + Jinja2 Dashboard  ─►  PostgreSQL
   polls every 10s       stores, deduplicates,            logs / portal status
                          rule-evaluates, decides,
                          auto-accepts (if safe),
                          runs poll-back
                                                │
                                                └─► Telegram Bot (optional)
```

**Key features** (see [Architecture](#architecture) for details):

- 7-state booking lifecycle: `new → accepted_candidate → {auto_accepted, manually_accepted, failed_to_accept, expired}` or `new → rejected`. State machine enforced server-side; invalid moves return HTTP 409.
- Deterministic rule engine — minimum value, allowed pickup / vehicle / customer categories, auto-accept flag. No AI, no external calls.
- Centralised selector fallback chains (Layout A → Layout B → graceful failure).
- Autonomous poll-back loop that marks stale `accepted_candidate` bookings as `expired` when the job disappears from the portal.
- Operator dashboard with manual Confirm button + screenshot / HTML evidence on failure.
- Optional Telegram notifications (graceful no-op when credentials missing).
- 114 unit + integration tests (82 API + 32 worker). All pass in Docker.

---

## Prerequisites

You need **three things** installed on your machine before anything else.

### 1. Docker Engine + Docker Compose

- macOS: install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) (it bundles Compose). Docker Desktop also gives you a working Linux VM — you do **not** need Colima if you use Docker Desktop.
- Linux: install Docker Engine + the `docker compose` plugin from your distro's package manager.
- Windows: install Docker Desktop with WSL2 backend.

Verify:

```bash
docker --version
docker compose version
```

### 2. (macOS only) Colima if you do not use Docker Desktop

If you prefer Colima over Docker Desktop:

```bash
brew install colima docker docker-compose
colima start
```

This README assumes `docker compose` works without further setup.

### 3. (Optional) uv for local Python work

Most users will never need this — every test command in this README runs inside Docker, not on your laptop. Install `uv` only if you want to run `pytest` outside Docker for fast iteration:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Hardware baseline

- macOS / Linux x86_64 or Apple Silicon.
- 4 GB RAM free (Chromium + Postgres + FastAPI + Worker all at once).
- 2 GB free disk for Docker images + Postgres volume.

---

## Quick Start

```bash
git clone git@github.com:PhamNgocTan24/rider_portal_watcher.git
cd rider_portal_watcher

# Optional: copy .env.example → .env if you want to override defaults.
# Defaults work out of the box.
cp .env.example .env

docker compose up --build
```

Wait until all 4 containers are healthy (about 20–40 seconds on first build, 5–10 on subsequent runs). You can watch the healthcheck in a second terminal:

```bash
watch -n 1 'docker ps --format "{{.Names}}\t{{.Status}}"'
```

When everything is up:

| Service | URL | Notes |
|---|---|---|
| Fake partner portal | http://localhost:3000 | Login: `demo` / `demo123` |
| Admin dashboard | http://localhost:8000 | No login (MVP) |
| Swagger API docs | http://localhost:8000/docs | OpenAPI 3 |
| PostgreSQL | `localhost:5432` | `rideportal:rideportal` / db `rideportal` |

To stop everything:

```bash
docker compose down
# Add `-v` to also wipe the Postgres volume (deletes all bookings + rules + logs)
docker compose down -v
```

---

## How to handle environment variables

The project uses **one** environment file, `.env.example`, committed to the repo. Defaults are tuned for `docker compose up` and require zero edits. If you want to override, create a real `.env` (gitignored).

### The simple rule

**All environment variables live in `.env.example`. The file you create locally is `.env`. Never commit `.env`.**

```bash
cp .env.example .env   # one-time per clone
$EDITOR .env           # change only what you need
```

`.gitignore` already contains `.env` so you cannot accidentally commit it.

### What `.env.example` provides

It defines every variable the four services need:

```
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=rideportal
POSTGRES_USER=rideportal
POSTGRES_PASSWORD=***           # demo value, not a real password
DATABASE_URL=postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal

API_BASE_URL=http://api:8000
FAKE_PORTAL_BASE_URL=http://fake-portal:3000
FAKE_PORTAL_USERNAME=demo
FAKE_PORTAL_PASSWORD=***        # demo value, matches the fake portal seed

WORKER_POLL_INTERVAL_SECONDS=10
WORKER_HEADLESS=true
WORKER_SCREENSHOT_DIR=/app/artifacts/screenshots
WORKER_HTML_SNAPSHOT_DIR=/app/artifacts/html_snapshots

TELEGRAM_BOT_TOKEN=***         # empty → Telegram disabled, app continues normally
```

### How each service reads the env

- **api** and **worker**: `env_file: .env.example` in `docker-compose.yml`. The env is loaded into every container at start.
- **postgres** and **fake-portal**: read compose-level `environment` only (no `.env` file lookup), with the same defaults so the stack stays consistent.

If you want to run a single service **outside** Docker (for live-reload during API development, for example):

```bash
cd apps/api
uv sync
DATABASE_URL=postgresql+asyncpg://rideportal:rideportal@localhost:5432/rideportal \
  uvicorn app.main:app --reload --port 8000
```

Note the `localhost` hostname — when you bypass Compose networking you must point at `localhost`, not `postgres`.

### Telegram: optional, with safe default

If `TELEGRAM_BOT_TOKEN` is empty (or `TELEGRAM_CHAT_ID` is empty), the `app/services/telegram.py` service logs `telegram_disabled` once at startup and every notification becomes a no-op. The app does not crash.

To enable real Telegram alerts:

1. Create a bot via [@BotFather](https://t.me/botfather), get the token.
2. Send any message to your bot, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your `chat_id`.
3. Set both in `.env` and restart the worker + api.

---

## How to install / update dependencies

The repo pins every dependency. There is **nothing to install on your host** for normal usage — Docker builds everything.

### When does the host need to install something?

- You want to run `pytest` outside Docker for fast iteration.
- You want to add a new dependency to one of the three services.

### Adding a new dependency

Each service is a separate `uv` project:

```bash
# Pick a service
cd apps/api          # or apps/worker or apps/fake_partner_portal

# Add the dep (uv edits pyproject.toml + uv.lock)
uv add httpx==0.27.0

# Commit both files
git add pyproject.toml uv.lock
git commit -m "deps(api): add httpx"
```

The next `docker compose up --build` will install the new dep inside the container automatically (Dockerfile runs `uv sync --no-dev` from the project files).

### Why `uv` and not `pip` + `requirements.txt`?

`uv` is faster, locks deterministically, and is already what the Dockerfiles use. The lockfile (`uv.lock`) is the source of truth for reproducible builds.

### Local Python work without Docker (optional, dev only)

```bash
cd apps/api
uv venv --python 3.11
source .venv/bin/activate
uv sync --all-groups     # includes dev (pytest, ruff, etc.)
pytest tests/ -v
```

This works for the api and worker services. Skip the `fake_partner_portal` for tests — it has no test suite.

### Upgrading a pinned dep

```bash
cd apps/api
uv add --upgrade httpx
```

Or edit `pyproject.toml` directly. Either way, the lockfile updates. Commit both.

---

## Running tests

The test suite is **114 tests** (82 API + 32 worker), all running inside Docker — no local Python install needed.

### Run the full suite

```bash
# 1. Start Postgres + API (worker tests do not need any service running;
#    API tests need Postgres)
docker compose up -d postgres
sleep 10                         # let Postgres finish initialising

# 2. Build the api image (includes test deps via uv sync)
docker compose build api

# 3. Run API tests
docker compose run --rm api sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio httpx -q
  /app/.venv/bin/pytest /app/tests/ -v
"

# 4. Run worker tests (no DB required)
docker compose build worker
docker compose run --rm worker sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio -q
  /app/.venv/bin/pytest /app/tests/ -v
"
```

You should see:

```
API:   82 passed in 1.2s
Worker: 32 passed in 0.1s
Total: 114 passed
```

### Run a single test file or test

```bash
# Just the rule engine
docker compose run --rm api /app/.venv/bin/pytest /app/tests/test_rule_engine.py -v

# Just the state-machine tests
docker compose run --rm api /app/.venv/bin/pytest /app/tests/test_booking_status.py -v

# A specific test class
docker compose run --rm worker /app/.venv/bin/pytest /app/tests/test_poll_back.py::TestPollBackExpiredCases -v
```

### What is covered

- **`apps/api/tests/test_rule_engine.py`** (12 tests): every branch of the rule engine, portal safety override.
- **`apps/api/tests/test_booking_api.py`** (13 tests): create, dedup, list, filter, exists, mark auto-accepted, 404 paths.
- **`apps/api/tests/test_logs_api.py`** (8 tests): create log with metadata, list, validation.
- **`apps/api/tests/test_status_endpoints.py`** (16 tests): the four status-mutation endpoints (`/auto-accepted`, `/manually-accepted`, `/failed-to-accept`, `/expired`) including state-machine enforcement returning 409.
- **`apps/api/tests/test_booking_status.py`** (33 tests): `is_valid_status_transition`, all valid + invalid moves, terminal states, `ACCEPTED_STATUSES` and `TERMINAL_STATUSES` sets, defensive behaviour on `None` / garbage input.
- **`apps/worker/tests/test_selector_fallback.py`** (8 tests): `find_first_available` order, fallback chain, `SelectorNotFoundError`.
- **`apps/worker/tests/test_portal_safety.py`** (4 tests): degraded portal pauses auto-accept, failure-evidence payload.
- **`apps/worker/tests/test_api_client.py`** (12 tests): `booking_exists`, `list_accepted_candidates`, `mark_failed_to_accept`, `mark_expired` — including the 4xx / network-error / wrong-URL guard tests.
- **`apps/worker/tests/test_poll_back.py`** (8 tests): empty candidate list, portal list failure, gone vs still-there, mixed batch, portal-name filtering, log payload.

### What is NOT covered (and why)

- Real third-party portals — explicitly out of scope per REQUIREMENTS §5.
- Browser E2E tests of the fake portal — covered by manual demo checklist instead; Playwright is a heavy dependency for a one-page portal.
- Visual regression, load testing — out of scope for the MVP.

---

## Full system flow

### 1. Startup

```
docker compose up --build
        │
        ├─► postgres starts, tables created via Alembic migrations
        ├─► fake-portal starts, seeds 2 demo rides, exposes /health
        ├─► api starts, runs migrations, exposes /health
        └─► worker starts, waits for api + fake-portal /health to return 200
```

The worker does not start polling until both `api` and `fake-portal` are reachable. This is enforced by a retry loop inside `apps/worker/app/main.py`.

### 2. Worker login

```
worker
  └─► Playwright launches Chromium (headless)
  └─► navigates to http://fake-portal:3000/login
  └─► fills username=demo, password=demo123
  └─► clicks Sign In
  └─► waits for redirect to /rides (confirms login success)
  └─► POST /api/logs  ← "portal_login_success"
```

Selector fallback chain at login (priority order):

```
Username:  [data-testid="input-username"]  →  #username  →  input[name="username"]
Password:  [data-testid="input-password"]  →  #password  →  input[name="password"]
Button:    [data-testid="btn-login"]       →  button[type="submit"]  →  .btn-primary
```

### 3. Poll loop (every 10 seconds by default)

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
  ├─[Step D]─► if API returns auto_accept_allowed=true AND status=accepted_candidate:
  │              ├─► navigate to /rides/{id}
  │              ├─► click [data-testid="btn-accept"] (or fallback .accept-btn)
  │              ├─► on success: POST /api/bookings/{id}/auto-accepted
  │              └─► on failure: POST /api/bookings/{id}/failed-to-accept
  │                            + log the exception reason
  │
  └─[Step E]─► POLL-BACK: GET /api/bookings?status=accepted_candidate
                 ├─ for each candidate still on the portal → leave it alone
                 └─ for each candidate GONE from the portal →
                       POST /api/bookings/{id}/expired
                       + log "poll_back_job_gone"
```

### 4. API processes the booking

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
  │       2. booking_value >= min?    → if not: status=rejected
  │       3. pickup in allow-list?    → if not: status=rejected
  │       4. vehicle in allow-list?   → if not: status=rejected
  │       5. customer in allow-list?  → if not: status=rejected
  │       6. All passed              → status=accepted_candidate, auto_accept_allowed=rule.auto_accept
  │
  ├─► UPDATE booking_jobs SET status=..., decision_reason=...
  │       (state machine validates the transition; invalid → 409)
  │
  ├─► Telegram notification sent (if TELEGRAM_BOT_TOKEN configured)
  │
  └─► Return BookingDecisionResponse to worker
```

### 5. State machine — 7 statuses, 6 valid moves

```
new ──────────────────┬──► accepted_candidate ──┬──► auto_accepted
                      │                          ├──► manually_accepted
                      │                          ├──► failed_to_accept
                      │                          └──► expired
                      └──► rejected
```

5 terminal states: `auto_accepted`, `manually_accepted`, `failed_to_accept`, `rejected`, `expired`. All block further transitions; the API returns HTTP 409 on any attempt to mutate a terminal row.

`ACCEPTED_STATUSES = {auto_accepted, manually_accepted}` — the dashboard's `/bookings/accepted` page filters by this set.
`TERMINAL_STATUSES` = the 5 terminal states — used by future analytics / cleanup jobs.

### 6. Broken layout flow

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

## How to verify it works

Step-by-step checklist that exercises the whole stack. All commands assume `docker compose up -d` has finished and the four containers are healthy.

### Step 1 — Confirm all services are healthy

```bash
curl http://localhost:8000/health
curl http://localhost:3000/health
```

Expected:

```json
{"status":"ok","service":"api","database":"ok"}
{"status":"ok","service":"fake-portal","layout":"layout_a"}
```

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

### Step 6 — Test broken layout detection

```bash
curl -X POST http://localhost:3000/admin/switch-layout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "layout=broken"
```

After ~15 seconds:

```bash
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

### Step 7 — Check dashboard pages all load

```bash
for path in "/" "/bookings/new" "/bookings/accepted" "/bookings/rejected" "/rules" "/logs" "/portal-status"; do
  echo -n "$path → "
  python3 -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000$path'); print(r.status)"
done
```

Expected: all return `200`.

### Step 8 — Test rejected booking rule

```bash
curl -X POST http://localhost:3000/admin/switch-layout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "layout=layout_a"

# Publish a job that should be rejected (value too low + bad pickup)
curl -X POST http://localhost:3000/admin/publish-job \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "pickup=Zone+6+Romford&dropoff=Luton&value=20&vehicle=MPV&customer_category=leisure&pickup_time=2026-06-07T03:00:00Z&notes="
```

After worker polls:

```bash
curl "http://localhost:8000/api/bookings?status=rejected" | python3 -m json.tool
```

Expected: booking with `"decision_reason": "Booking value below minimum ..."` or `"Pickup location is not allowed"`.

### Step 9 — Test manual confirm from dashboard

1. Open http://localhost:8000/bookings/new
2. Find a row with status `accepted_candidate`.
3. Click the Confirm button. The row should immediately disappear from this view and appear under http://localhost:8000/bookings/accepted with status `manually_accepted`.

### Step 10 — Test poll-back expiry

1. Publish a job (default params → becomes `accepted_candidate`).
2. Switch the fake portal to broken layout, then back to layout_a — this un-publishes nothing; instead, use the admin endpoint to delete the ride:
   ```bash
   # (no delete endpoint exists yet; use the layout switch trick)
   # Publish many jobs, wait one poll cycle, then switch layout to broken
   # for 30+ seconds. The portal will keep the jobs but the worker will
   # not refresh its list. To force expiry:
   # Restart the fake-portal container to clear its in-memory ride list.
   docker compose restart fake-portal
   ```
3. Wait 20 seconds, then:
   ```bash
   curl "http://localhost:8000/api/bookings?status=expired" | python3 -m json.tool
   ```
4. Expected: each previously-`accepted_candidate` booking now has `status: "expired"` and a `decision_reason` containing "no longer available on portal".

---

## Demo scenarios

### Scenario A — Full happy path

1. `docker compose up --build`
2. Open http://localhost:3000, log in as `demo/demo123`.
3. Admin Controls → Publish Job (defaults).
4. Check http://localhost:8000/bookings/accepted within 15 seconds.

### Scenario B — Rejected booking

1. Publish a job with Value=20, Pickup=Zone 6 Romford.
2. Check http://localhost:8000/bookings/rejected.

### Scenario C — Layout B (fallback selectors)

1. Admin Controls → Switch layout → Layout B.
2. Publish a job.
3. Check http://localhost:8000/logs for `selector_fallback_used` entries.

### Scenario D — Broken portal

1. Admin Controls → Switch layout → Broken.
2. Check http://localhost:8000/portal-status — degraded, auto-accept paused.
3. Switch back to Layout A — worker recovers on next poll.

### Scenario E — Auto-accept enabled

```bash
docker exec rider_portal_watcher-postgres-1 \
  psql -U rideportal -d rideportal \
  -c "UPDATE business_rules SET auto_accept = true WHERE name = 'Default Rule';"
```

Publish a qualifying job → booking status becomes `auto_accepted`.

### Scenario F — Manual confirm

1. Publish a job (default rule has `auto_accept=false` by default, so the booking lands in `accepted_candidate`).
2. Open http://localhost:8000/bookings/new.
3. Click Confirm on the row → row moves to `/bookings/accepted` with status `manually_accepted`.

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
│  - Click accept (if allowed) │        │  - State machine │
│  - Poll-back: expire stale   │        │  - Store result  │
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
| Auto-accept click fails | Booking moves to `failed_to_accept` with the failure reason — never stuck in `accepted_candidate` |
| Booking vanishes from portal (taken by competitor) | Poll-back loop transitions it to `expired` on the next cycle |
| Operator clicks Confirm on a terminal row | API returns 409; row state unchanged |

---

## Project structure

```
rideportal_watcher/
├── apps/
│   ├── api/                       FastAPI backend + dashboard
│   │   ├── app/
│   │   │   ├── main.py            FastAPI app factory
│   │   │   ├── config.py          Pydantic Settings
│   │   │   ├── database.py        SQLAlchemy async engine
│   │   │   ├── models/            ORM: BookingJob, BookingStatus, BusinessRule, AutomationLog, PortalStatus
│   │   │   ├── schemas/           Pydantic request/response
│   │   │   ├── repositories/      DB queries (no raw SQL in routes)
│   │   │   ├── services/          rule_engine, booking_service, telegram
│   │   │   ├── routers/           bookings, logs, portal_status, dashboard
│   │   │   ├── templates/         Jinja2 HTML pages (7 dashboard pages)
│   │   │   └── static/            CSS + small JS for table controls
│   │   ├── alembic/               Migrations (0001 schema, 0002 seed default rule)
│   │   ├── tests/                 82 pytest tests
│   │   ├── Dockerfile             python:3.11-slim + uv
│   │   └── pyproject.toml
│   │
│   ├── worker/                    Playwright automation
│   │   ├── app/
│   │   │   ├── main.py            Poll loop, login, auto-accept, poll-back
│   │   │   ├── config.py          Pydantic Settings
│   │   │   ├── api_client.py      HTTP client to API
│   │   │   └── portal_adapters/
│   │   │       ├── base.py        find_first_available, SelectorNotFoundError, save_screenshot, save_html_snapshot
│   │   │       ├── fake_ride_portal.py  Full Playwright adapter
│   │   │       └── selectors.py   Centralised fallback selector lists
│   │   ├── tests/                 32 pytest tests
│   │   ├── Dockerfile             python:3.11-slim + Chromium + Playwright
│   │   └── pyproject.toml
│   │
│   └── fake_partner_portal/       Controlled fake booking portal
│       ├── app/
│       │   ├── main.py            FastAPI app: login, rides, accept, publish, switch-layout
│       │   ├── state.py           In-memory ride store + layout mode
│       │   └── templates/         Login, rides list, ride detail (Layout A + B + Broken)
│       ├── Dockerfile
│       └── pyproject.toml
│
├── artifacts/                     Screenshots + HTML snapshots on failure
│   ├── screenshots/
│   └── html_snapshots/
│
├── docker-compose.yml             4 services + healthchecks
├── .env.example                   All env vars, demo values
├── .gitignore
│
├── AGENTS.md                      AI coding agent instructions
├── REQUIREMENTS.md                Product requirements
├── ARCHITECTURE.md                System architecture
├── TASKS.md                       Task-by-task implementation log
├── TESTING.md                     Test strategy + test cases per feature
├── README.md                      ← you are here
└── LICENSE
```

---

## Environment variables reference

| Variable | Default | Used by | Description |
|---|---|---|---|
| `POSTGRES_HOST` | `postgres` | api | Postgres host (use `localhost` outside Compose) |
| `POSTGRES_PORT` | `5432` | api | Postgres port |
| `POSTGRES_DB` | `rideportal` | api | Database name |
| `POSTGRES_USER` | `rideportal` | api | Database user |
| `POSTGRES_PASSWORD` | `***` (demo) | api, postgres | Database password — replace in production |
| `DATABASE_URL` | `postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal` | api | Full async SQLAlchemy URL |
| `API_BASE_URL` | `http://api:8000` | worker | URL the worker calls |
| `FAKE_PORTAL_BASE_URL` | `http://fake-portal:3000` | worker | URL the worker scrapes |
| `FAKE_PORTAL_USERNAME` | `demo` | worker | Fake portal login |
| `FAKE_PORTAL_PASSWORD` | `***` (demo) | worker | Fake portal login |
| `WORKER_POLL_INTERVAL_SECONDS` | `10` | worker | How often to poll the portal |
| `WORKER_HEADLESS` | `true` | worker | Run Chromium headless; set `false` to watch the browser |
| `WORKER_SCREENSHOT_DIR` | `/app/artifacts/screenshots` | worker | Where to save failure screenshots |
| `WORKER_HTML_SNAPSHOT_DIR` | `/app/artifacts/html_snapshots` | worker | Where to save failure HTML |
| `TELEGRAM_BOT_TOKEN` | empty | api, worker | Optional — leave empty to disable Telegram |
| `TELEGRAM_CHAT_ID` | empty | api, worker | Optional — leave empty to disable Telegram |

---

## Troubleshooting

### `docker compose up` hangs at "Container …  Starting" forever

Most likely Postgres is unhealthy. Check:

```bash
docker logs rider_portal_watcher-postgres-1
```

If you see `FATAL: database files are incompatible with server`, your `postgres_data` volume was created by a different Postgres major version. Wipe and restart:

```bash
docker compose down -v
docker compose up --build
```

### Worker logs say `AttributeError: 'ApiClient' object has no attribute 'booking_exists'`

You are on an old commit before `task-20-fix-worker-api-client`. Update your branch:

```bash
git fetch origin
git checkout task-20-fix-worker-api-client
git pull
```

### Tests fail with `ModuleNotFoundError: No module named 'app'`

The Dockerfile uses `uv sync --no-dev` — `pytest` is not in the production image. Install it inside the container at test time:

```bash
docker compose run --rm api sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio httpx -q
  /app/.venv/bin/pytest /app/tests/ -v
"
```

### Telegram errors spam the logs

If you have an old `TELEGRAM_BOT_TOKEN` that was revoked, the API will return 401 on every notification. Set `TELEGRAM_BOT_TOKEN=` (empty) in `.env` and restart — the app will log `telegram_disabled` once and stop calling.

### Port 3000 or 8000 already in use

Stop whatever is on those ports, or change the published ports in `docker-compose.yml`:

```yaml
  api:
    ports:
      - "8080:8000"   # host 8080 → container 8000
  fake-portal:
    ports:
      - "3001:3000"
```

Remember to also update `API_BASE_URL` and `FAKE_PORTAL_BASE_URL` in `.env` if you change the host ports — the worker uses these to find the services.

### Chromium crashes with `libnss3.so: cannot open shared object file`

This usually means the worker image was built on a different OS. Rebuild without cache:

```bash
docker compose build worker --no-cache
```

### Portainer / alternative Docker frontends

The repo only tests with vanilla Docker Engine + Compose. Other frontends (Podman, OrbStack, etc.) may need adjusted volume mounts or network names.

---

## License

This is a portfolio project — feel free to read, fork, and learn from it. If you use it as a starting point for a client engagement, please retain the AGENTS.md / REQUIREMENTS.md / ARCHITECTURE.md so future maintainers can orient themselves.
