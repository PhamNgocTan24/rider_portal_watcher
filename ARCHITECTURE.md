# ARCHITECTURE.md — RidePortal Watcher

## 1. System Overview

RidePortal Watcher has four main components:

```text
Fake Partner Portal
        ↑
        │ browser automation
        │
Playwright Worker ───── HTTP ─────> FastAPI API + Dashboard ─────> PostgreSQL
                                      │
                                      └──────────── Telegram Bot API
```

The fake portal simulates a third-party ride booking portal. The Playwright worker logs in to the fake portal, monitors available rides, extracts booking details, and sends data to the API. The API stores booking data, evaluates business rules, sends notifications, and powers the dashboard.

## 2. Service Responsibilities

### 2.1 Fake Partner Portal

Purpose: safe controlled demo target for browser automation.

Responsibilities:

- Render login page.
- Render ride list page.
- Render ride detail page.
- Allow publishing demo jobs.
- Allow accepting jobs.
- Switch between `layout_a`, `layout_b`, and `broken`.

It intentionally simulates portal layout changes so the worker can demonstrate fallback selector and failure handling.

### 2.2 Playwright Worker

Purpose: automation runtime.

Responsibilities:

- Login to portal.
- Poll available rides.
- Extract booking details.
- Send booking payload to API.
- Receive/interpret API decision.
- Click accept only when safe.
- Run health checks.
- Capture evidence on failures.
- Report automation logs.

### 2.3 FastAPI API and Dashboard

Purpose: system backend and operator interface.

Responsibilities:

- Store booking data.
- Deduplicate bookings.
- Evaluate business rules.
- Store automation logs.
- Track portal health.
- Send Telegram notifications.
- Render dashboard pages.
- Expose JSON endpoints for worker.

### 2.4 PostgreSQL

Purpose: durable storage.

Stores:

- Bookings.
- Rules.
- Logs.
- Portal status.

## 3. Data Flow

### 3.1 New Booking Detection

```text
Worker opens /rides
→ extracts booking IDs
→ compares with seen IDs / API state
→ opens /rides/{id}
→ extracts detail fields
→ POST /api/bookings
→ API deduplicates
→ API evaluates rules
→ API stores decision
→ API sends Telegram
→ dashboard updates
```

### 3.2 Auto-Accept Flow

```text
API returns accepted_candidate + auto_accept_allowed=true
→ worker checks local portal health is healthy
→ worker opens booking detail page
→ worker verifies accept button selector
→ worker clicks accept
→ worker reports auto_accept success to API
→ API marks booking auto_accepted
→ Telegram notification sent
```

Auto-accept must not happen if portal is degraded or critical selectors are missing.

### 3.3 Layout Change Flow

```text
Fake portal switches Layout A → Layout B
→ primary selector fails
→ fallback selector works
→ worker logs fallback selector usage
→ booking extraction continues
```

### 3.4 Broken Layout Flow

```text
Fake portal switches to broken layout
→ worker cannot find required selectors
→ worker raises SelectorNotFoundError
→ screenshot captured
→ HTML snapshot saved
→ automation log sent to API
→ portal status marked degraded
→ Telegram alert sent
→ auto-accept paused
```

## 4. Core Data Model

### 4.1 booking_jobs

Fields:

- `id`
- `external_booking_id`
- `portal_name`
- `pickup_location`
- `dropoff_location`
- `booking_value`
- `vehicle_category`
- `customer_category`
- `pickup_time`
- `status`
- `decision_reason`
- `raw_payload`
- `detected_at`
- `updated_at`

Unique constraint:

- `(portal_name, external_booking_id)`

### 4.2 business_rules

Fields:

- `id`
- `name`
- `min_booking_value`
- `allowed_pickup_locations`
- `allowed_vehicle_categories`
- `allowed_customer_categories`
- `auto_accept`
- `is_active`
- `created_at`
- `updated_at`

### 4.3 automation_logs

Fields:

- `id`
- `portal_name`
- `level`
- `step`
- `message`
- `external_booking_id`
- `screenshot_path`
- `html_snapshot_path`
- `metadata`
- `created_at`

### 4.4 portal_status

Fields:

- `id`
- `portal_name`
- `status`
- `last_checked_at`
- `last_error`
- `auto_accept_paused`
- `updated_at`

Status values:

- `healthy`
- `degraded`
- `down`

## 5. API Endpoint Design

### Worker-facing endpoints

- `POST /api/bookings`
- `POST /api/bookings/{id}/auto-accepted`
- `GET /api/bookings/exists?portal_name=&external_booking_id=`
- `POST /api/logs`
- `POST /api/portal-status`
- `GET /api/portal-status/{portal_name}`

### Dashboard endpoints

- `GET /`
- `GET /bookings/new`
- `GET /bookings/accepted`
- `GET /bookings/rejected`
- `GET /rules`
- `POST /rules`
- `POST /rules/{id}`
- `GET /logs`
- `GET /portal-status`

## 6. Resilience Design

The system uses multiple resilience layers:

1. Portal adapter pattern isolates each portal.
2. Centralized selectors reduce maintenance cost.
3. Fallback selector chains reduce breakage risk.
4. Health checks detect broken portals early.
5. Screenshot and HTML snapshots speed up debugging.
6. Portal degraded status pauses unsafe auto-accept.
7. Telegram alerts notify maintainers immediately.
8. Logs provide audit trail.

## 7. Local Deployment

Use Docker Compose:

```text
postgres
api
worker
fake-portal
```

Startup order:

1. PostgreSQL starts.
2. API waits for database and runs migrations.
3. Fake portal starts.
4. Worker waits for API and fake portal health endpoints.
5. Worker begins polling.

## 8. Production Notes

This MVP is not production deployment, but it demonstrates production thinking.

Real production improvements would include:

- Real secrets manager.
- Authentication for dashboard.
- Background job framework.
- Metrics and monitoring.
- More robust retry policies.
- Per-portal worker instances.
- Access control and audit logs.
- Real geocoding/radius rules.
- CI/CD pipeline.
