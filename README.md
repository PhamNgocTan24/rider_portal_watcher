# RidePortal Watcher

A portfolio-grade MVP demonstrating **production-minded browser automation** for a transportation booking portal. Built with Python, Playwright, FastAPI, PostgreSQL, and Docker.

## What It Demonstrates

- Playwright async browser automation with fallback selectors
- Business rule engine that evaluates and decides on bookings
- Automatic failure detection with screenshot + HTML snapshot evidence
- Portal health monitoring with degraded-state detection
- Auto-accept paused when portal is broken or degraded
- FastAPI backend with Jinja2 dashboard
- Telegram notifications (optional)
- Full Docker Compose stack with Alembic migrations

---

## Quick Start

```bash
git clone git@github.com:PhamNgocTan24/rider_portal_watcher.git
cd rider_portal_watcher
docker compose up --build
```

| Service | URL |
|---|---|
| Fake partner portal | http://localhost:3000 |
| API + Dashboard | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

---

## Demo Credentials

| Field | Value |
|---|---|
| Portal username | `demo` |
| Portal password | `demo123` |

---

## Demo Scenarios

### 1 — Happy Path: Accepted Booking

1. Open http://localhost:3000/login and log in with `demo / demo123`
2. Click **⚙ Admin Controls** at the bottom of the page
3. Click **Publish Job** with default values (Heathrow → Mayfair, £120, Executive Saloon, corporate)
4. Wait ~10 seconds for the worker to poll
5. Open http://localhost:8000/bookings/accepted — the booking appears with status `accepted_candidate` and reason `Matched all active rules`
6. Open http://localhost:8000/logs — worker log entries confirm extraction and evaluation
7. Open http://localhost:8000/portal-status — portal shows `healthy`

### 2 — Rejected Booking

1. Publish a job with **Value = 30**, **Pickup = Zone 6, Romford**
2. After worker polls, open http://localhost:8000/bookings/rejected
3. Booking shows status `rejected` with reason `Booking value below minimum` or `Pickup location is not allowed`

### 3 — Layout B Fallback Selectors

1. In Admin Controls, switch layout to **Layout B**
2. Publish a new job
3. Worker detects and extracts the job using fallback CSS selectors (no code change required)
4. Check http://localhost:8000/logs — entries show `selector_fallback_used`
5. Booking appears in dashboard as normal

### 4 — Broken Layout: Failure Evidence + Portal Degraded

1. In Admin Controls, switch layout to **Broken**
2. Worker detects the broken layout via health check
3. Portal status immediately becomes `degraded`, auto-accept paused
4. Open http://localhost:8000/portal-status — status shows `degraded`
5. Switch layout back to **Layout A** — worker recovers automatically on the next poll

### 5 — Auto-Accept (optional)

To enable auto-accept, update the default rule in the DB:

```sql
UPDATE business_rules SET auto_accept = true WHERE name = 'Default Rule';
```

Then publish a qualifying job — the worker will click accept on the portal and the booking status becomes `auto_accepted`.

---

## Running Tests

```bash
# Worker tests (no DB needed)
docker compose run --rm worker sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio -q
  /app/.venv/bin/pytest tests/ -v"

# API tests (requires postgres running)
docker compose run --rm \
  -e DATABASE_URL=postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal \
  api sh -c "
  uv pip install --python /app/.venv/bin/python pytest pytest-asyncio httpx -q
  /app/.venv/bin/pytest tests/ -v"
```

Expected: **45 tests pass** (33 API + 12 worker).

---

## Environment Variables

Copy `.env.example` to `.env` and adjust if needed. Defaults work with Docker Compose out of the box.

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | postgres://... | SQLAlchemy async URL |
| `FAKE_PORTAL_USERNAME` | `demo` | Portal login |
| `FAKE_PORTAL_PASSWORD` | `demo123` | Portal password |
| `WORKER_POLL_INTERVAL_SECONDS` | `10` | How often worker polls |
| `WORKER_HEADLESS` | `true` | Run Chromium headless |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Optional: Telegram bot token |
| `TELEGRAM_CHAT_ID` | *(empty)* | Optional: Telegram chat ID |

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is empty, the app logs `Telegram disabled` and continues without crashing.

---

## Project Structure

```
apps/
  api/                      FastAPI backend + Jinja2 dashboard
    app/
      models/               SQLAlchemy ORM models
      schemas/              Pydantic request/response schemas
      repositories/         DB access layer
      services/             Business logic (rule engine, Telegram)
      routers/              FastAPI route handlers
      templates/            Jinja2 HTML templates
    alembic/                Migrations
    tests/                  Pytest test suite
  worker/                   Playwright automation worker
    app/
      portal_adapters/      Portal-specific Playwright logic + selectors
    tests/
  fake_partner_portal/      Controlled fake booking portal (FastAPI)
    app/
      templates/            Login, rides list, ride detail
artifacts/
  screenshots/              Auto-saved on automation failure
  html_snapshots/           Auto-saved on automation failure
docker-compose.yml
.env.example
```

---

## Architecture Overview

```
Fake Partner Portal
       ↑
       │ Playwright browser automation
       │
Playwright Worker ──── HTTP ────▶ FastAPI API + Dashboard ────▶ PostgreSQL
                                         │
                                         └──── Telegram Bot API (optional)
```

1. Worker logs in to fake portal, polls `/rides` every N seconds
2. New booking IDs extracted → detail page scraped → POST to API
3. API deduplicates, evaluates business rules, stores decision
4. Telegram notification sent (if configured)
5. If `auto_accept_allowed=true` → worker clicks accept on portal
6. Dashboard shows bookings, rules, logs, portal status in real time

### Resilience

| Failure | Response |
|---|---|
| Portal layout changes (Layout B) | Fallback selectors used automatically |
| Broken layout | Screenshot + HTML captured, portal marked degraded, auto-accept paused |
| Single booking extraction fails | Logged, worker continues polling |
| Login fails | Logged as critical, portal marked down |
| Telegram unavailable | Logs warning, does not crash |
| Duplicate booking submitted | Returns `already_exists=true`, no duplicate row created |

---

## Implementation Status

| Task | Description | Status |
|---|---|---|
| 1 | Project skeleton | ✅ Done |
| 2 | Database setup | ✅ Done |
| 3 | Fake portal MVP | ✅ Done |
| 4 | Booking API | ✅ Done |
| 5 | Rule engine | ✅ Done |
| 6 | Telegram service | ✅ Done |
| 7 | Dashboard MVP | ✅ Done |
| 8 | Worker login | ✅ Done |
| 9 | Booking monitoring & extraction | ✅ Done |
| 10 | Auto-accept flow | ✅ Done |
| 11 | Selector fallback | ✅ Done |
| 12 | Broken layout + failure evidence | ✅ Done |
| 13 | Tests (45 passing) | ✅ Done |
| 14 | Documentation & demo script | ✅ Done |
| 15 | Final polish | ✅ Done |
