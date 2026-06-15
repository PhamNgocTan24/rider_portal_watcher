# REQUIREMENTS.md — RidePortal Watcher MVP

## 1. Product Summary

RidePortal Watcher is a portfolio-grade MVP for a transportation/chauffeur booking automation platform. It demonstrates a reliable browser automation system that logs in to a partner booking portal, monitors new ride requests, extracts booking details, evaluates configurable business rules, stores results in PostgreSQL, sends Telegram notifications, and provides an admin dashboard for jobs, rules, logs, and portal health.

This project is built as a demo for freelance opportunities involving Python, Playwright, Selenium-style automation, FastAPI, PostgreSQL, Docker, and production-minded maintenance of third-party portal automations.

The project must use a controlled fake partner portal for the full booking workflow. It must not automate real private portals unless explicit authorization and credentials are provided by the owner.

## 2. Core Business Problem

Transportation/chauffeur companies receive ride requests from multiple partner portals. Operators need to detect new requests quickly, evaluate whether a job is worth accepting, notify the team, and optionally accept jobs automatically when business rules allow it.

The biggest operational risk is that third-party portals change their layout and automation silently breaks. This MVP must prove that the system can detect failures, pause unsafe actions, capture debugging evidence, and alert maintainers.

## 3. Success Criteria

The demo is successful when a reviewer can run one command and see this flow:

1. Open fake partner portal.
2. Publish a new ride request.
3. Playwright worker logs in and detects the new ride.
4. Worker extracts booking details.
5. API stores booking in PostgreSQL.
6. Rule engine decides accepted_candidate or rejected.
7. Telegram notification is sent.
8. Dashboard shows new, accepted, rejected jobs and logs.
9. Portal layout is switched from Layout A to Layout B.
10. Worker continues using fallback selectors.
11. Portal is switched to broken layout.
12. Worker captures screenshot and HTML snapshot, logs the failure, sends Telegram alert, marks portal degraded, and pauses auto-accept.

## 4. In Scope

### 4.1 Fake Partner Portal

Build a local fake booking portal with:

- Login page.
- Available rides page.
- Ride detail page.
- Manual publish-job action.
- Accept ride action.
- Layout mode switcher: `layout_a`, `layout_b`, `broken`.
- Stable demo credentials.
- Seed data for accepted and rejected scenarios.

Required routes:

- `GET /login`
- `POST /login`
- `GET /rides`
- `GET /rides/{external_booking_id}`
- `POST /rides/{external_booking_id}/accept`
- `POST /admin/publish-job`
- `POST /admin/switch-layout`
- `GET /health`

### 4.2 Playwright Worker

The worker must:

- Use Python Playwright async API.
- Log in to the fake portal.
- Maintain browser session during polling.
- Poll available rides every configurable interval.
- Detect new external booking IDs.
- Open ride detail pages.
- Extract booking information.
- Send booking data to FastAPI.
- Optionally click accept only when the API/rule decision allows it.
- Run portal health checks.
- Use fallback selectors.
- Capture screenshots on failures.
- Save HTML snapshots on failures.
- Send automation logs to the API.
- Mark portal as degraded when critical selectors fail.
- Pause auto-accept when portal is degraded.

### 4.3 FastAPI Backend

The API must:

- Receive booking data from the worker.
- Deduplicate by `external_booking_id` and `portal_name`.
- Store bookings in PostgreSQL.
- Evaluate business rules.
- Store decision status and decision reason.
- Provide dashboard pages using Jinja2 templates.
- Provide JSON APIs for worker and dashboard.
- Send Telegram notifications.
- Store automation logs.
- Store portal status.

### 4.4 Business Rules

MVP rules:

- Minimum booking value.
- Allowed pickup locations.
- Allowed vehicle categories.
- Allowed customer categories.
- Auto-accept enabled/disabled.

Decision statuses (full state machine — see `apps/api/app/models/booking_status.py`):

- `new` — entry point, set on creation before rule evaluation
- `accepted_candidate` — rules passed, awaiting action (auto-accept or operator confirm)
- `auto_accepted` — terminal: worker clicked accept on portal successfully
- `manually_accepted` — terminal: operator confirmed via dashboard
- `failed_to_accept` — terminal: worker tried to auto-accept but job was gone / portal error
- `rejected` — terminal: rule-engine rejected the booking
- `expired` — terminal: poll-back detected the job is no longer available on the portal

State transition graph:

```text
new ──────────────────┬──► accepted_candidate ──┬──► auto_accepted
                      │                          ├──► manually_accepted
                      │                          ├──► failed_to_accept
                      │                          └──► expired
                      └──► rejected
```

Five terminal states have no outgoing transitions. Transitions are enforced by
`is_valid_status_transition(from, to)` in `booking_status.py` and the
repository raises `ValueError` on invalid moves (returned as HTTP 409 by
the API).

Decision reasons must be human-readable.

Example reasons:

- `Matched all active rules`
- `Booking value below minimum`
- `Pickup location is not allowed`
- `Vehicle category is not allowed`
- `Customer category is not allowed`
- `Portal degraded; auto-accept paused`
- `Operator confirmed acceptance via dashboard` (manually_accepted)
- `Auto-accept failed: <exception>` (failed_to_accept)
- `Job no longer available on portal — likely taken by another operator` (expired)

### 4.5 Telegram Notifications

Send notifications for:

- New booking detected.
- Booking accepted candidate.
- Booking auto-accepted.
- Booking rejected.
- Automation error.
- Portal degraded.

If Telegram credentials are missing, the app must not crash. It should log that Telegram is disabled.

### 4.6 Admin Dashboard

Use FastAPI + Jinja2. No complex SPA is required.

Required pages:

- `/` dashboard overview.
- `/bookings/new`
- `/bookings/accepted`
- `/bookings/rejected`
- `/rules`
- `/logs`
- `/portal-status`

Dashboard tables must show useful fields:

- Booking ID.
- Portal name.
- Pickup.
- Dropoff.
- Value.
- Vehicle.
- Customer category.
- Pickup time.
- Status.
- Decision reason.
- Detected at.
- Screenshot link when available.

### 4.7 PostgreSQL Persistence

Required tables:

- `booking_jobs`
- `business_rules`
- `automation_logs`
- `portal_status`

Use Alembic migrations. Do not rely on manual SQL only.

### 4.8 Docker Deployment

The full demo must run via:

```bash
docker compose up --build
```

Required services:

- `postgres`
- `api`
- `worker`
- `fake-portal`

The system should expose:

- Fake portal: `http://localhost:3000`
- API and dashboard: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### 4.9 Operator Actions and Lifecycle

The MVP supports three ways a booking reaches a terminal state:

**Auto-accept (worker-driven):** When the rule engine returns
`accepted_candidate` with `auto_accept_allowed=true`, the worker clicks
accept on the portal and POSTs to `/api/bookings/{id}/auto-accepted`. If
the click fails (job taken, portal error), the worker POSTs to
`/api/bookings/{id}/failed-to-accept` with the reason.

**Manual confirm (operator-driven):** The dashboard shows a Confirm
button for any booking in `accepted_candidate` status. Clicking it
POSTs to `/api/bookings/{id}/manually-accepted`, which transitions the
booking to `manually_accepted` and is also marked terminal.

**Poll-back (worker-driven, autonomous):** Every poll cycle, the worker
calls `GET /api/bookings?status=accepted_candidate` and checks each
against the portal's current job list. If a job is no longer listed
(taken by another operator, or timed out), the worker POSTs to
`/api/bookings/{id}/expired`. This prevents stale `accepted_candidate`
bookings from sitting in the dashboard forever.

## 5. Out of Scope

Do not implement these unless explicitly requested:

- Real private portal scraping.
- CAPTCHA bypass.
- MFA bypass.
- Cloudflare bypass.
- Payment actions.
- Real customer PII ingestion.
- Complex authentication for dashboard.
- Multi-tenant SaaS.
- Kubernetes.
- Real Google Maps distance/radius calculation.
- Email notification.
- Mobile app.
- AI/LLM decision-making.

## 6. Safety and Compliance Requirements

- Do not scrape or automate real third-party private portals without permission.
- Do not implement anti-bot bypass techniques.
- Do not store real passwords in source code.
- Do not commit `.env` files.
- Do not click accept when the portal is degraded.
- Do not click accept when rule confidence is unclear.
- Do not hide automation failures.
- Every automation error must be logged with enough context to debug.

## 7. Environment Variables

Provide `.env.example` with:

```env
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=rideportal
POSTGRES_USER=rideportal
POSTGRES_PASSWORD=rideportal
DATABASE_URL=postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal

API_BASE_URL=http://api:8000
FAKE_PORTAL_BASE_URL=http://fake-portal:3000
FAKE_PORTAL_USERNAME=demo
FAKE_PORTAL_PASSWORD=demo123

WORKER_POLL_INTERVAL_SECONDS=10
WORKER_HEADLESS=true
WORKER_SCREENSHOT_DIR=/app/artifacts/screenshots
WORKER_HTML_SNAPSHOT_DIR=/app/artifacts/html_snapshots

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## 8. Definition of Done

The MVP is complete only when:

- `docker compose up --build` starts all services.
- Fake portal is accessible.
- Dashboard is accessible.
- Worker logs in successfully.
- Worker detects at least one new ride.
- API stores booking in PostgreSQL.
- Rule engine evaluates booking.
- Telegram integration works or degrades gracefully when disabled.
- Dashboard shows booking and logs.
- Layout A and Layout B both work.
- Broken layout triggers screenshot, HTML snapshot, log, degraded status, and Telegram alert.
- README explains how to run demo scenarios.
- Tests pass.
