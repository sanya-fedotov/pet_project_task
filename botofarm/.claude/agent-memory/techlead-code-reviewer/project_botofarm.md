---
name: botofarm project context
description: Architecture, stack, and known issues for the botofarm microservice
type: project
---

FastAPI microservice for managing and leasing bot accounts. Clean Architecture: api → service (botfarm.py) → crud → model. PostgreSQL + SQLAlchemy async. JWT auth via python-jose.

Stack: Python 3.11, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, passlib/bcrypt, python-jose, Pydantic v2, pytest-asyncio, SQLite in-memory for tests.

**Known issues identified in code review (2026-03-30):**
- CORS wildcard with allow_credentials=True (security blocker)
- GET /api/v1/users is unauthenticated (access control blocker)
- /metrics endpoint is unauthenticated — exposes Prometheus internals
- DB error details leaked in 503 response from /health/ready
- Tests use SQLite instead of PostgreSQL — SELECT FOR UPDATE SKIP LOCKED is NOT supported by SQLite, so concurrency logic is untested
- python-jose is unmaintained (CVE risks); recommended replacement is PyJWT
- passlib is also in maintenance mode; consider python-bcrypt directly
- No password length/complexity validation in UserCreate schema
- No rate limiting on /auth/token (brute force risk)
- Token has no `jti` claim — no revocation support
- lock_user returns 404 when no users available — semantically should be 503 or 409
- free_users releases ALL locks atomically without filtering by project_id
- No .dockerignore — tests/secrets may end up in image
- Dockerfile has no non-root USER directive
- No index on (project_id, env, domain, locktime) for filtered lock queries
- mypy strict=false, no CI config present

**Why:** This is a bot-farm leasing service; concurrency correctness and auth security are critical.
**How to apply:** Pay extra attention to auth bypass paths, SQLite/PostgreSQL behavioral differences in tests, and lock logic correctness.
