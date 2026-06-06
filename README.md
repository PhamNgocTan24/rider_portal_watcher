# RidePortal Watcher

A portfolio-grade MVP demonstrating production-minded browser automation for a transportation booking portal. Built with Python, Playwright, FastAPI, PostgreSQL, and Docker.

## What It Does

1. A **Playwright worker** logs into a fake ride-booking portal and polls for new ride requests.
2. New bookings are sent to the **FastAPI backend**, which deduplicates, evaluates configurable business rules, and stores results in **PostgreSQL**.
3. Operators view jobs, rules, logs, and portal health on an **admin dashboard**.
4. **Telegram notifications** are sent for new bookings, decisions, and automation errors.
5. When the portal layout changes, the worker uses **fallback selectors** automatically.
6. When the portal is broken, the worker **captures a screenshot and HTML snapshot**, marks the portal degraded, pauses auto-accept, and alerts via Telegram.

## Quick Start

```bash
git clone <repo-url>
cd rider_portal_watcher
docker compose up --build
```

Services:

| Service | URL |
|---|---|
| Fake portal | http://localhost:3000 |
| API + Dashboard | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

## Demo Credentials

| Field | Value |
|---|---|
| Username | `demo` |
| Password | `demo123` |

## Environment Variables

Copy `.env.example` to `.env` and adjust if needed. The defaults work out of the box with Docker Compose.

```bash
cp .env.example .env
```

## Demo Scenarios

> Full demo steps will be added in Task 14. Current build is Task 1 skeleton.

## Project Structure

```
apps/
  api/              FastAPI backend and dashboard
  worker/           Playwright automation worker
  fake_partner_portal/  Controlled fake booking portal
artifacts/
  screenshots/      Failure screenshots (auto-created by worker)
  html_snapshots/   Failure HTML snapshots (auto-created by worker)
docker-compose.yml
.env.example
```

## Running Tests

```bash
# All tests
pytest

# Service-specific
cd apps/api && pytest
cd apps/worker && pytest
```

## Implementation Status

| Task | Description | Status |
|---|---|---|
| 1 | Project skeleton | ✅ Done |
| 2 | Database setup | ⬜ Pending |
| 3 | Fake portal MVP | ⬜ Pending |
| 4 | Booking API | ⬜ Pending |
| 5 | Rule engine | ⬜ Pending |
| 6 | Telegram service | ⬜ Pending |
| 7 | Dashboard MVP | ⬜ Pending |
| 8 | Worker login | ⬜ Pending |
| 9 | Booking monitoring | ⬜ Pending |
| 10 | Auto-accept flow | ⬜ Pending |
| 11 | Selector fallback | ⬜ Pending |
| 12 | Broken layout handling | ⬜ Pending |
| 13 | Tests | ⬜ Pending |
| 14 | Docs and demo script | ⬜ Pending |
| 15 | Final polish | ⬜ Pending |
