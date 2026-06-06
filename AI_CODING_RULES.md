# AI_CODING_RULES.md — Implementation Rules and Conventions

## 1. Core Principle

Build a small, reliable, demoable system. Do not over-engineer. The main value is proving production-minded browser automation: monitoring, extraction, rule decision, notification, logging, and resilience to portal layout changes.

## 2. Recommended Repository Structure

```text
rideportal-watcher/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── repositories/
│   │   │   ├── services/
│   │   │   ├── routers/
│   │   │   ├── templates/
│   │   │   └── static/
│   │   ├── alembic/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── worker/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── api_client.py
│   │   │   ├── portal_adapters/
│   │   │   │   ├── base.py
│   │   │   │   ├── fake_ride_portal.py
│   │   │   │   └── selectors.py
│   │   │   └── services/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── fake_partner_portal/
│       ├── app/
│       │   ├── main.py
│       │   ├── state.py
│       │   ├── templates/
│       │   └── static/
│       ├── Dockerfile
│       └── pyproject.toml
├── docs/
├── artifacts/
│   ├── screenshots/
│   └── html_snapshots/
├── docker-compose.yml
├── .env.example
├── REQUIREMENTS.md
├── AGENTS.md
├── ARCHITECTURE.md
├── TASKS.md
├── TESTING.md
└── README.md
```

## 3. Naming Conventions

- Python modules: `snake_case`.
- Classes: `PascalCase`.
- Functions and variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Database tables: `snake_case` plural-ish names where appropriate.
- Enum values: lower snake case strings.

Examples:

- `BookingJob`
- `BusinessRule`
- `AutomationLog`
- `PortalStatus`
- `accepted_candidate`
- `auto_accepted`

## 4. Python Style

- Use type hints.
- Keep functions short.
- Prefer dependency injection for services.
- Avoid global mutable state except fake portal demo state if deliberately simple.
- Avoid broad `except Exception` unless logging and re-raising or safe recovery is implemented.
- Use `datetime` with timezone awareness when possible.
- Use decimal for money values where possible.

## 5. FastAPI Rules

Use routers:

- `bookings.py`
- `rules.py`
- `logs.py`
- `portal_status.py`
- `dashboard.py`

Keep business logic out of routers. Routers call services. Services call repositories.

Preferred layering:

```text
router -> service -> repository -> database
```

## 6. Database and Migrations

Use SQLAlchemy 2.x and Alembic.

Required constraints:

- Unique constraint on `(portal_name, external_booking_id)` in `booking_jobs`.
- Unique constraint on `portal_name` in `portal_status`.

Required timestamps:

- `created_at`
- `updated_at` where relevant.

Use JSONB for raw payload and metadata fields.

## 7. Rule Engine Contract

The rule engine receives a booking-like object and active business rule.

It returns:

```python
@dataclass
class RuleDecision:
    status: str
    reason: str
    auto_accept_allowed: bool
```

Rules are evaluated in this order:

1. Portal health safety check.
2. Minimum booking value.
3. Pickup location allow-list.
4. Vehicle category allow-list.
5. Customer category allow-list.
6. Auto-accept flag.

First failure returns rejected or safety-blocked status with reason.

## 8. Playwright Selector Strategy

Centralize selectors in `selectors.py`.

Selector priority:

1. `data-testid`
2. ARIA role / accessible name
3. Stable visible text
4. Semantic CSS class
5. XPath only as last resort

Example:

```python
BOOKING_CARD_SELECTORS = [
    '[data-testid="booking-card"]',
    'article.ride-request-card',
    '.booking-card',
]
```

Implement a reusable selector helper:

```python
async def find_first_available(page, selectors: list[str], timeout_ms: int = 3000):
    ...
```

The helper must log which selector worked. If none works, raise a custom `SelectorNotFoundError` with the selector list.

## 9. Portal Adapter Contract

All portal adapters must implement:

```python
class PortalAdapter(Protocol):
    async def login(self) -> None: ...
    async def health_check(self) -> PortalHealthResult: ...
    async def list_available_jobs(self) -> list[PortalJobSummary]: ...
    async def extract_job_detail(self, external_booking_id: str) -> PortalBookingDetail: ...
    async def accept_job(self, external_booking_id: str) -> None: ...
```

Only `FakeRidePortalAdapter` is required for MVP.

## 10. Error Handling Rules

For automation errors:

- Capture screenshot.
- Save HTML snapshot.
- Send log to API.
- Mark portal degraded for critical failures.
- Send Telegram alert via API.
- Continue worker loop after safe cooldown.

Critical failures:

- Cannot login.
- Cannot find booking list.
- Cannot extract required booking fields.
- Cannot determine whether accept action is safe.

Non-critical failures:

- One booking detail page temporarily unavailable.
- Telegram notification disabled.
- Duplicate booking already exists.

## 11. Telegram Rules

Telegram service must be optional.

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing:

- Do not crash.
- Log `Telegram disabled: missing configuration`.

## 12. Logging Rules

Use structured logs. Include:

- `portal_name`
- `step`
- `external_booking_id` when available
- `level`
- `message`
- `metadata`

Examples of steps:

- `worker_start`
- `portal_login`
- `list_jobs`
- `extract_job_detail`
- `rule_evaluation`
- `auto_accept`
- `selector_failure`
- `portal_health_check`

## 13. Docker Rules

`docker compose up --build` must work from repo root.

Do not require manual local PostgreSQL installation.

Use healthchecks where helpful.

Worker should wait for API and fake portal to be available before starting polling.

## 14. Documentation Rules

Update README when:

- Setup command changes.
- Demo scenario changes.
- New environment variable is added.
- New service is added.

Update architecture docs when:

- Data flow changes.
- Service boundaries change.
- Database schema changes.

## 15. Quality Bar

This is a portfolio demo. It must look professional.

Avoid:

- Dead routes.
- Empty placeholder pages.
- TODOs without explanation.
- Hardcoded secrets.
- Silent failures.
- One giant file.
- Random dependencies.
