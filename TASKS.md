# TASKS.md — Incremental Implementation Plan

## Rule for AI Coding Agents

Implement tasks in order. Do not jump ahead. Each task must leave the project runnable.

## Task 1 — Project Skeleton

Create:

- Repo structure.
- `docker-compose.yml`.
- `.env.example`.
- Empty FastAPI API service.
- Empty worker service with startup log.
- Empty fake portal service with `/health`.
- Basic README with run command.

Acceptance:

- `docker compose up --build` starts all services.
- API `/health` returns OK.
- Fake portal `/health` returns OK.

## Task 2 — Database Setup

Implement:

- SQLAlchemy setup.
- Alembic setup.
- Models for `BookingJob`, `BusinessRule`, `AutomationLog`, `PortalStatus`.
- Initial migration.
- Database health check.

Acceptance:

- Migrations run.
- Tables exist.
- API can connect to PostgreSQL.

## Task 3 — Fake Partner Portal MVP

Implement:

- Login page.
- Session/cookie demo login.
- Rides list page.
- Ride detail page.
- Publish demo job route.
- Accept job route.
- Layout A HTML with `data-testid` selectors.

Acceptance:

- User can login with demo credentials.
- User can publish a job.
- User can view job list and detail.
- User can accept a job manually.

## Task 4 — Booking API

Implement:

- `POST /api/bookings`.
- Deduplication by portal + external booking ID.
- `GET /api/bookings` with status filter.
- Basic booking schemas.

Acceptance:

- Worker or curl can create booking.
- Duplicate booking does not create duplicate row.
- Booking list endpoint works.

## Task 5 — Rule Engine

Implement:

- Rule engine service.
- Default active rule seed.
- Minimum booking value rule.
- Allowed pickup locations rule.
- Allowed vehicle categories rule.
- Allowed customer categories rule.
- Decision status and reason.

Acceptance:

- Accepted booking receives `accepted_candidate`.
- Rejected booking receives `rejected` and reason.
- Unit tests cover major decisions.

## Task 6 — Telegram Service

Implement:

- Telegram notification service.
- Optional config behavior.
- Booking decision notifications.
- Automation error notification function.

Acceptance:

- Missing Telegram config does not crash.
- With config present, service attempts to send.
- Logs show Telegram disabled or sent.

## Task 7 — Dashboard MVP

Implement pages:

- Overview.
- New jobs.
- Accepted jobs.
- Rejected jobs.
- Rules.
- Logs.
- Portal status.

Acceptance:

- Dashboard displays stored bookings.
- Rules page displays active rule.
- Logs page displays automation logs.

## Task 8 — Playwright Worker Login

Implement:

- Playwright async setup.
- Fake portal adapter.
- Login flow.
- Worker config.
- API client.

Acceptance:

- Worker starts browser.
- Worker logs in to fake portal.
- Worker logs login success to API.

## Task 9 — Booking Monitoring and Extraction

Implement:

- List available jobs.
- Extract booking summaries.
- Open detail page.
- Extract required fields.
- POST booking to API.
- Poll loop.

Acceptance:

- Publishing a fake portal job results in booking row in API DB.
- Dashboard shows the booking.

## Task 10 — Auto-Accept Flow

Implement:

- API response returns decision and auto-accept flag.
- Worker clicks accept only if safe.
- Worker reports auto-accepted status to API.

Acceptance:

- Accepted candidate is clicked in fake portal.
- API booking status becomes `auto_accepted`.
- Rejected jobs are not accepted.

## Task 11 — Selector Fallback

Implement:

- Centralized selectors.
- `find_first_available` helper.
- Layout B in fake portal.
- Switch layout route.
- Log fallback selector usage.

Acceptance:

- Layout A works.
- Layout B works without code change.
- Logs show fallback selector usage when Layout B is active.

## Task 12 — Broken Layout and Failure Evidence

Implement:

- Broken layout mode in fake portal.
- Custom `SelectorNotFoundError`.
- Screenshot capture.
- HTML snapshot capture.
- Automation log with paths.
- Portal degraded status.
- Auto-accept pause.
- Telegram error alert.

Acceptance:

- Broken layout does not crash entire system permanently.
- Screenshot file is created.
- HTML snapshot file is created.
- Portal status becomes degraded.
- Dashboard shows log and degraded status.

## Task 13 — Tests

Add/complete tests for:

- Rule engine.
- Booking dedupe.
- Booking API.
- Selector fallback helper.
- Portal degraded safety.

Acceptance:

- `pytest` passes.

## Task 14 — Documentation and Demo Script

Update:

- README.
- Demo scenarios.
- Maintenance guide.
- Resilience explanation.

Acceptance:

- A reviewer can run the project from README.
- README includes demo credentials.
- README includes video script or demo steps.

## Task 15 — Final Polish

Check:

- No secrets committed.
- `.env.example` complete.
- Docker works from clean checkout.
- Logs are readable.
- Dashboard is usable.
- Demo scenarios work.

Acceptance:

- Project is ready for GitHub and Upwork proposal.

## Task 16 — BookingStatus Enum and State Machine

Implemented (in commit 9dc5152, branch `task-booking-status-enum`):

- New file `apps/api/app/models/booking_status.py` with the `BookingStatus`
  enum and `is_valid_status_transition(from, to)`.
- `BookingRepository.update_status()` validates transitions, raises
  `ValueError` on invalid moves.
- `BookingService` gains `mark_manually_accepted`, `mark_failed_to_accept`,
  `mark_expired`.
- Three new API endpoints (see ARCHITECTURE §5).
- `ACCEPTED_STATUSES` and `TERMINAL_STATUSES` exported for dashboard.

Acceptance:

- All 33 API tests still pass.
- Invalid transitions return 409 from the API.

## Task 17 — Poll-Back Loop (Autonomous Expiry)

Implemented (same commit):

- `apps/worker/app/main.py:run_poll_back()` — every poll cycle, lists
  `accepted_candidate` bookings and marks any whose external_id is no
  longer on the portal as `expired`.
- `ApiClient.list_accepted_candidates()` — fetches the candidate list.
- `ApiClient.mark_expired(booking_id, reason)` — transitions a booking.

Acceptance:

- A booking that disappears from the portal becomes `expired` within
  one poll cycle.
- A booking still on the portal is left alone.

## Task 18 — Manual Confirm from Dashboard

Implemented (same commit):

- Dashboard `bookings.html` shows a Confirm button only for
  `accepted_candidate` rows.
- Clicking Confirm POSTs to `/manually-accepted` with a JS confirm dialog.
- The button is hidden for every other status.

Acceptance:

- Operator can move a row from `accepted_candidate` to
  `manually_accepted` via the dashboard.
- An already-terminal row does not show the button.

## Task 19 — Documentation Alignment and Test Coverage

Resolve the gap between code and docs after Tasks 16-18 landed without
docs updates.

Acceptance:

- REQUIREMENTS.md lists all 7 statuses and the state machine graph.
- ARCHITECTURE.md documents Manual Confirm, Poll-Back, and Failed
  Auto-Accept flows; the state machine table; the new endpoints.
- TASKS.md reflects Tasks 16-19 (this section).
- TESTING.md gains test cases for transitions, manual confirm, poll-back.

## Task 20 — Fix Worker ApiClient.booking_exists() Bug

Found via audit: `main.py:113` calls `api.booking_exists(...)` but the
method was never defined in `ApiClient` — only orphan code at the end
of the file referencing unbound variables. Worker would AttributeError
on the first poll cycle.

Fix: add `booking_exists(portal_name, external_booking_id) -> bool` to
`ApiClient`, removing the orphan fragment.

Tests: 12 new tests in `apps/worker/tests/test_api_client.py` covering
`booking_exists`, `list_accepted_candidates`, `mark_failed_to_accept`,
`mark_expired`. All 24 worker tests now pass (12 prior + 12 new).
