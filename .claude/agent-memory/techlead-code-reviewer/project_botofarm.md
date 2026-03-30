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

STATUS after third review (2026-03-30 full pass):

All previously-flagged remaining issues are now RESOLVED:
- Startup probe endpoint exists: GET /api/v1/health/startup
- Helm charts present: helm/botofarm/ with Chart.yaml, values.yaml, deployment.yaml, service.yaml, configmap.yaml, secret.yaml
- CI workflow present: .github/workflows/ci.yml (ruff, mypy, pytest)
- monitoring/prometheus.yml present
- middleware registration order documented with inline comment explaining Starlette reverse order
- mypy: disallow_untyped_defs=true, disallow_any_generics=true, warn_unused_ignores=true, disallow_incomplete_defs=true (strict=false but meaningful checks enabled)

REMAINING ISSUES after third review:
- .env committed to repo with SECRET_KEY placeholder — BLOCKER
- values.yaml has hardcoded SECRET_KEY/METRICS_TOKEN defaults "change-me-in-production" — BLOCKER (secrets in VCS even if placeholders)
- Dockerfile does not exclude .env: .dockerignore lists .env but only as first entry; needs verification that build context actually excludes it
- Prometheus service not in docker-compose.yml (monitoring/ files exist but are not wired up)
- CI skips test_lock_pg.py (testcontainers tests need Docker) — no --ignore flag, but tests are only excluded by pytest path selection (tests/unit/ tests/api/)
- No rate limiting on /auth/token — brute-force vector
- free_users unscoped (all projects) — spec gap; no project_id filter
- lock_user unscoped — no env/domain/project_id filter params
- No pagination on GET /users
- Helm chart lacks Ingress template
- passlib in maintenance mode (minor)
- lock_user SQLite vs PostgreSQL timezone awareness gap in tests (tz-aware workaround in test)

**Why:** Bot-farm leasing service; concurrency correctness and auth security are critical.
**How to apply:** In future reviews, focus on the remaining spec gaps (Helm, CI, monitoring) and any new auth/lock logic.
