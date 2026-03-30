---
name: botofarm project context
description: Architecture, stack, and known issues for the botofarm microservice (reviewed 2026-03-30, fixes verified 2026-03-30)
type: project
---

FastAPI microservice for managing and leasing bot accounts for E2E testing. Clean Architecture: api -> service (botfarm.py) -> crud -> model. PostgreSQL + SQLAlchemy 2.0 async. JWT auth via PyJWT (migrated from python-jose).

Stack: Python 3.11, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, passlib/bcrypt, PyJWT, Pydantic v2, pytest-asyncio, SQLite in-memory for most tests, testcontainers PostgreSQL for lock integration tests, prometheus-fastapi-instrumentator.

**Status after second review (2026-03-30 fix pass):**

RESOLVED from first review:
- auth.py now delegates to service.login() — Clean Architecture restored
- .gitignore created with .env and standard Python exclusions
- alembic.ini sqlalchemy.url is blank
- lock_user raises HTTP 404 (not 503)
- testcontainers PostgreSQL fixtures added (conftest.py), test_lock_pg.py exists
- /metrics guarded by middleware (localhost or Bearer METRICS_TOKEN)
- CORS allow_origins reads from settings.cors_origins
- created_at has server_default=func.now() in model and server_default=sa.text("now()") in migration
- Dead noqa:F401 import removed from auth.py
- synchronize_session=False added to free_users bulk update
- PyJWT replaces python-jose in requirements.txt and security.py
- locktime index added to model and migration
- mypy disallow_untyped_defs and disallow_any_generics added
- TokenData.sub is EmailStr; no # type: ignore in dependencies.py

REMAINING ISSUES (after fix pass):
- .env is committed to the repo (contains SECRET_KEY, even if only a test value)
- mypy strict=false; warn_unused_ignores, no_implicit_optional, disallow_incomplete_defs not set (partial fix)
- middleware registration order: _guard_metrics is registered AFTER Instrumentator().expose(); FastAPI middleware runs in reverse order so guard is outermost — correct behavior but fragile and undocumented
- When METRICS_TOKEN is empty AND caller is not localhost, endpoint returns 403 rather than 404; this leaks the existence of the endpoint (minor)
- No rate limiting on /auth/token
- No startup probe endpoint (CLAUDE.md spec mentions startup, liveness, readiness)
- No Helm charts (required by spec)
- No .github/workflows CI (required by spec)
- No monitoring/ directory with prometheus.yml / grafana (required by spec)
- free_users releases all locks across all projects (no project_id scoping) — possible spec gap
- lock_user has no project_id/env/domain filter params — possible spec gap
- passlib is in maintenance mode (minor)

**Why:** Bot-farm leasing service; concurrency correctness and auth security are critical.
**How to apply:** In future reviews, focus on the remaining spec gaps (Helm, CI, monitoring) and any new auth/lock logic.
