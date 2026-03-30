---
name: Botofarm DX infrastructure
description: Key facts about the CI/CD and DX setup for the Botofarm project
type: project
---

DX infrastructure fully set up as of 2026-03-30.

**Stack:** Python 3.11, FastAPI, SQLAlchemy 2 async, PostgreSQL 14, pytest, ruff, mypy.

**CI pipeline (`.github/workflows/ci.yml`):**
- Stage 1 `lint`: ruff check + ruff format --check + mypy (runs on every push/PR)
- Stage 2 `test`: unit + API tests against SQLite in-memory, with `--cov-fail-under=75`; coverage XML uploaded as artifact
- Stage 3 `test-integration`: `test_lock_pg.py` only, uses testcontainers (Docker-in-Docker on ubuntu-latest); env var `TESTCONTAINERS_RYUK_DISABLED=true` required

**Docker pipeline (`.github/workflows/docker.yml`):**
- Pushes to `ghcr.io/<repo>` only on push to `main` or semver tags; PRs only build (no push)
- Uses `docker/metadata-action` for automatic tagging

**Pre-commit hooks (`.pre-commit-config.yaml`):**
- `pre-commit-hooks` v5.0.0: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-merge-conflict, check-added-large-files, mixed-line-ending
- `detect-secrets` v1.5.0 with baseline at `.secrets.baseline` (baseline is clean — no findings)
- `ruff-pre-commit` v0.15.8: ruff + ruff-format
- `mypy` mirror v1.19.1: runs on `app/` only (pass_filenames=false), additional_dependencies include pydantic, sqlalchemy, fastapi

**Coverage:** actual 92% against a 75% gate. `[tool.coverage]` config in `pyproject.toml`.

**Known pre-existing test bug:** `tests/api/test_metrics.py::test_metrics_blocked_without_token` and `test_metrics_blocked_with_wrong_token` fail because they expect 403 when `METRICS_TOKEN=""`, but the middleware intentionally opens the endpoint when the token is unset. The middleware behavior is correct per the spec.

**Why:** DX infra was set up to enforce quality before the project is graded. Coverage gate, pre-commit hooks, and CI stages all enforce the graded requirements.

**How to apply:** Any future changes to CI or test config should maintain the 3-stage pipeline ordering and keep coverage above 75%.
