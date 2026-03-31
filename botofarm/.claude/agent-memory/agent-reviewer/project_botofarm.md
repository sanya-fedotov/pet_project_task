---
name: Botofarm Project Context
description: Architecture, stack, and review history for Botofarm microservice (updated 2026-03-30)
type: project
---

Botofarm is a FastAPI async microservice for managing bot accounts in E2E testing. Clean Architecture is followed well (api → service → crud → model).

Stack: Python 3.11+, FastAPI, SQLAlchemy 2 async/asyncpg, PostgreSQL 14, Pydantic v2, Alembic, passlib[bcrypt], PyJWT, prometheus-fastapi-instrumentator, pytest/httpx/pytest-asyncio, testcontainers. Test env runs Python 3.13.

**Second review round (2026-03-30) — targeted fixes from agents**

All three previously flagged issues have been resolved:

1. BLOCKER resolved: metrics test/middleware contradiction.
   - Tests now patch `settings.metrics_token` via `monkeypatch.setattr` on the live singleton.
   - Middleware reads `settings.metrics_token` at request time, so patching works.
   - Behavior: empty token → open endpoint (correct). All 50 tests pass.

2. SUGGESTION resolved: gauge init from DB on startup.
   - `_sync_locked_gauge()` in `lifespan` queries active locks (locktime IS NOT NULL AND > now()-TTL) and calls `users_locked_current.set(count)`.
   - Logic is correct and consistent with how the service layer increments/decrements.

3. SUGGESTION resolved: Helm `required` on METRICS_TOKEN removed.
   - `secret.yaml` now renders METRICS_TOKEN without `required`, defaulting to empty string.

**Remaining issues after second round:**

- SUGGESTION: `values.yaml` has `SECRET_KEY: ""` and `secret.yaml` has `required` for SECRET_KEY. The `required` guard in Helm only fires when the key is *absent*, not when it is an *empty string*. So `helm install` without `--set env.SECRET_KEY=...` produces a secret with `SECRET_KEY=""` silently — no error, but app starts with a dangerously weak signing key.

- SUGGESTION: initContainer (alembic upgrade head) has no mechanism to wait for Postgres readiness. If the DB pod is still starting, the initContainer will fail and Kubernetes will restart the pod (expected Kubernetes behavior, but the delay can be significant on first deploy). A `pg_isready` check loop or a separate init step would make deploys more robust.

- NITPICK: Test suite emits InsecureKeyLengthWarning (JWT HMAC key < 32 bytes). The test SECRET_KEY is too short for HS256. Not a production risk but adds noise to CI output.

**What is correct (stable, do not re-raise in future reviews):**
- Clean Architecture boundaries respected.
- SELECT FOR UPDATE SKIP LOCKED implementation correct.
- bcrypt password hashing, JWT auth, no password exposure in responses.
- .env not git-tracked.
- Async style consistent (no blocking calls).
- Test coverage: unit + API (SQLite) + PG integration (testcontainers).
- pre-commit hooks: detect-secrets, ruff, mypy.

**Why:** Multiple agent iterations (backend, metrics, test, ci/cd agents). Final targeted fix review.
**How to apply:** In future reviews, focus on the SECRET_KEY empty-string Helm gap and the initContainer DB readiness gap.
