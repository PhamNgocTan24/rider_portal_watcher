# TESTING.md — Test Strategy

## 1. Goal

Tests should prove the core business logic and automation safety behavior. The MVP does not need exhaustive browser E2E coverage, but it must test the parts that would be risky in production.

## 2. Test Commands

From repo root:

```bash
pytest
```

For service-specific tests, use:

```bash
cd apps/api && pytest
cd apps/worker && pytest
```

Docker validation:

```bash
docker compose up --build
```

## 3. Required Unit Tests

### 3.1 Rule Engine

Test cases:

- Booking value above minimum + allowed categories returns `accepted_candidate`.
- Booking value below minimum returns `rejected`.
- Pickup location not allowed returns `rejected`.
- Vehicle category not allowed returns `rejected`.
- Customer category not allowed returns `rejected`.
- Auto-accept disabled returns accepted candidate but `auto_accept_allowed=false`.
- Portal degraded prevents auto-accept.

### 3.2 Booking Deduplication

Test cases:

- First booking insert creates row.
- Same `portal_name + external_booking_id` does not create duplicate.
- Duplicate can update fields if implementation chooses upsert.

### 3.3 Selector Fallback

Test cases:

- First selector works.
- First selector fails, second selector works.
- All selectors fail raises `SelectorNotFoundError`.
- Error includes selector list.

This can be tested with mocks or a lightweight Playwright page.

### 3.4 Portal Safety

Test cases:

- Degraded portal status prevents auto-accept.
- Missing accept selector prevents auto-accept.
- Critical extraction failure creates automation log.

### 3.5 Booking Status State Machine

Test cases for `is_valid_status_transition` in
`apps/api/app/models/booking_status.py`:

- `new → accepted_candidate` is valid.
- `new → rejected` is valid.
- `new → auto_accepted` is **invalid** (must go through `accepted_candidate`).
- `accepted_candidate → auto_accepted` is valid.
- `accepted_candidate → manually_accepted` is valid.
- `accepted_candidate → failed_to_accept` is valid.
- `accepted_candidate → expired` is valid.
- `accepted_candidate → rejected` is **invalid** (rule evaluation already happened).
- `auto_accepted → anything` is **invalid** (terminal).
- `manually_accepted → anything` is **invalid** (terminal).
- `failed_to_accept → anything` is **invalid** (terminal).
- `rejected → anything` is **invalid** (terminal).
- `expired → anything` is **invalid** (terminal).
- `is_valid_status_transition("invalid_string", "new")` is `False`.
- `ACCEPTED_STATUSES` = `{auto_accepted, manually_accepted}`.
- `TERMINAL_STATUSES` = `{auto_accepted, manually_accepted, failed_to_accept, rejected, expired}`.

Also test that the repository's `update_status()` raises `ValueError`
on invalid transitions, and that the API translates that to HTTP 409.

### 3.6 Manual Confirm and Failed Auto-Accept Endpoints

Test cases for the four status-mutation endpoints:

- `POST /api/bookings/{id}/auto-accepted` — accepted_candidate → auto_accepted (200).
- `POST /api/bookings/{id}/manually-accepted` — accepted_candidate → manually_accepted (200).
- `POST /api/bookings/{id}/manually-accepted` on an auto_accepted booking returns 409.
- `POST /api/bookings/{id}/manually-accepted` on a rejected booking returns 409.
- `POST /api/bookings/{id}/failed-to-accept` with a reason payload — accepted_candidate → failed_to_accept (200).
- `POST /api/bookings/{id}/expired` with a reason payload — accepted_candidate → expired (200).
- `POST /api/bookings/{id}/expired` on a rejected booking returns 409.
- All four endpoints return 404 for an unknown booking_id.
- All four endpoints return 400 for a non-UUID booking_id.

### 3.7 Worker Poll-Back Logic

For `run_poll_back()` in `apps/worker/app/main.py` (or its extracted
pure-function equivalent if you refactor):

- If portal has no `accepted_candidate` candidates, the function does
  nothing (no API call, no error).
- If a candidate's `external_booking_id` is still on the portal, the
  function does not call `mark_expired`.
- If a candidate's `external_booking_id` is missing from the portal,
  the function calls `mark_expired(booking_id, reason)`.
- If the portal's `list_available_jobs()` call raises, the function
  swallows the error (does not propagate).
- If a candidate belongs to a different portal_name, the function
  ignores it (the worker only manages its own portal).

### 3.8 Worker ApiClient Methods

For `apps/worker/app/api_client.py`:

- `booking_exists(portal, id)` returns `True` when API says exists.
- `booking_exists(portal, id)` returns `False` when API says no.
- `booking_exists(portal, id)` returns `False` on 404.
- `booking_exists(portal, id)` returns `False` on network error.
- `booking_exists(portal, id)` uses correct query params.
- `list_accepted_candidates()` returns the list returned by the API.
- `list_accepted_candidates()` returns `[]` on error.
- `list_accepted_candidates()` filters by `status=accepted_candidate`.
- `mark_failed_to_accept(id, reason)` POSTs to the right URL with the
  right JSON body.
- `mark_expired(id, reason)` POSTs to the right URL with the right JSON
  body.
- Both mutation methods swallow network errors (worker must not crash).

## 4. Required API Tests

Test endpoints:

- `POST /api/bookings`
- `GET /api/bookings`
- `GET /api/bookings?status=rejected`
- `POST /api/logs`
- `POST /api/portal-status`
- `GET /api/portal-status/{portal_name}`

Use test database or transaction rollback fixtures.

## 5. Manual Demo Test Checklist

Run:

```bash
docker compose up --build
```

Then verify:

1. Open `http://localhost:3000/login`.
2. Login with `demo/demo123`.
3. Publish accepted scenario job.
4. Check dashboard booking appears.
5. Check decision is accepted candidate or auto accepted.
6. Publish rejected scenario job.
7. Check rejected page and reason.
8. Switch portal to Layout B.
9. Publish job and confirm worker still extracts.
10. Switch portal to broken layout.
11. Confirm screenshot saved.
12. Confirm HTML snapshot saved.
13. Confirm portal status degraded.
14. Confirm auto-accept paused.
15. Confirm logs show selector failure.
16. Open `/bookings/new`, click the Confirm button on a row — verify
    it transitions to `manually_accepted` and disappears from this view.
17. Wait for poll-back to run (one poll cycle) — verify a stale
    `accepted_candidate` row that was unpublished from the portal
    becomes `expired`.

## 6. What Not to Test in MVP

Do not spend MVP time on:

- Real third-party portals.
- CAPTCHA flows.
- Cloudflare bypass.
- Visual regression.
- Load testing.
- Multi-user dashboard authentication.

## 7. Definition of Passing

The project is considered passing when:

- Unit tests pass.
- API tests pass.
- Docker demo starts.
- Manual demo checklist works.
- Current test count baseline: **45 passing** (33 API + 12 worker).
  After the test-coverage work in Task 19-22 the count grows to
  **57+ passing** (33 API + 24 worker, plus state-machine, manual-
  confirm, poll-back tests).
