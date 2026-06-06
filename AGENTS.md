# AGENTS.md — AI Coding Agent Instructions

## 1. Role

You are an AI coding agent working on RidePortal Watcher, a portfolio-grade MVP for Python Playwright automation in a transportation booking context.

Your job is to implement the project safely, incrementally, and according to the source-of-truth documents. Do not improvise major scope. Do not build unrelated features.

## 2. Source of Truth

Before writing code, read these files in order:

1. `REQUIREMENTS.md`
2. `ARCHITECTURE.md`
3. `AI_CODING_RULES.md`
4. `TASKS.md`
5. `TESTING.md`

If files conflict, follow this priority:

1. `REQUIREMENTS.md`
2. `AGENTS.md`
3. `ARCHITECTURE.md`
4. `AI_CODING_RULES.md`
5. `TASKS.md`
6. `TESTING.md`

## 3. Operating Mode

Work in small implementation slices. Each slice must leave the project runnable.

Do not attempt to implement the entire project in one large change.

Preferred workflow for each task:

1. Read relevant docs.
2. Identify files to change.
3. Implement the smallest working version.
4. Add or update tests.
5. Run formatting/lint/test commands when available.
6. Update docs if behavior changes.
7. Summarize what changed and what remains.

## 4. Non-Negotiable Guardrails

- Do not automate real private third-party portals.
- Do not add CAPTCHA bypass, MFA bypass, Cloudflare bypass, fingerprint evasion, or anti-bot bypass.
- Do not commit secrets.
- Do not hardcode Telegram token, database passwords, or portal passwords outside `.env.example` demo values.
- Do not introduce paid external services.
- Do not replace PostgreSQL with SQLite.
- Do not replace Playwright with Selenium unless explicitly requested.
- Do not build a complex frontend SPA. Use FastAPI + Jinja2 unless told otherwise.
- Do not click accept when portal status is degraded.
- Do not click accept when selectors are uncertain.
- Do not let worker crash permanently on one booking failure.
- Do not hide automation failures.
- Do not store real PII.

## 5. Project Architecture Rules

The system has four services:

- `api`: FastAPI backend and dashboard.
- `worker`: Playwright automation worker.
- `fake-portal`: controlled fake booking portal.
- `postgres`: database.

Use Docker Compose for local orchestration.

The worker communicates with the API over HTTP. The fake portal must not write directly to the main API database unless explicitly required for seed/demo convenience.

## 6. Coding Standards

- Use Python 3.11+.
- Use async where appropriate, especially Playwright and DB access.
- Use type hints for public functions.
- Use Pydantic models for request/response schemas.
- Use SQLAlchemy models for persistence.
- Use Alembic for migrations.
- Use structured logging.
- Keep functions small and testable.
- Prefer explicit names over clever abstractions.
- Keep portal selectors centralized.
- Keep business rules in a dedicated service.

## 7. Playwright Rules

Use Playwright async API.

Do:

- Use portal adapter pattern.
- Use centralized fallback selectors.
- Use role/label/data-testid selectors when possible.
- Add timeouts.
- Capture screenshot on failure.
- Save HTML snapshot on failure.
- Log the failed step.
- Mark portal degraded after critical failure.

Do not:

- Use brittle `nth-child` selectors unless no alternative exists.
- Click dangerous actions without rule approval.
- Continue auto-accept after critical extraction failure.
- Suppress exceptions without logging.

## 8. Business Rule Rules

The rule engine must return both:

- decision status
- human-readable reason

The rule engine must be deterministic. It must not call external services. It must not use AI.

Auto-accept is allowed only when:

- active rule matches,
- booking is accepted candidate,
- `auto_accept` is enabled,
- portal status is healthy,
- required selectors are available.

## 9. Database Rules

Use these core entities:

- `BookingJob`
- `BusinessRule`
- `AutomationLog`
- `PortalStatus`

Use UUID primary keys. Use `external_booking_id + portal_name` for deduplication.

Store raw extracted booking payload in JSONB for debugging.

## 10. Dashboard Rules

Dashboard must be simple and useful. Avoid over-design.

Required pages:

- Overview.
- New jobs.
- Accepted jobs.
- Rejected jobs.
- Rules.
- Logs.
- Portal status.

No user login is required for the MVP.

## 11. Testing Rules

Tests must cover:

- Rule engine decisions.
- Booking deduplication.
- API booking creation.
- Selector fallback utility.
- Portal degraded behavior.

Use pytest.

Do not skip tests silently.

## 12. Completion Checklist for Every Task

A task is done only when:

- The implementation matches the relevant requirement.
- The app still starts.
- Tests are added or updated when applicable.
- No secret is committed.
- Docs are updated when behavior changes.
- The next task remains clear.

## 13. Preferred Response Format for Coding Agent

After each task, report:

```text
Implemented:
- ...

Files changed:
- ...

Validation:
- ...

Notes / next steps:
- ...
```
