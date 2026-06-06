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
