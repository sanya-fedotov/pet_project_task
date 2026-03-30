# Botofarm

[![CI](https://github.com/your-org/botofarm/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/botofarm/actions/workflows/ci.yml)
[![Docker](https://github.com/your-org/botofarm/actions/workflows/docker.yml/badge.svg)](https://github.com/your-org/botofarm/actions/workflows/docker.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Coverage >= 75%](https://img.shields.io/badge/coverage-%E2%89%A575%25-brightgreen)](#testing)

RESTful microservice that manages a pool of bot accounts for E2E testing.
It hands out credentials on demand, guarantees exclusive access per account via atomic row-level locking, and releases them automatically when the lock TTL expires.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11 |
| Docker | 24.x |
| Docker Compose | 2.x (plugin, not standalone) |
| make | any |

> For local development without Docker you additionally need PostgreSQL 14+ running locally and the `pre-commit` CLI (`pip install pre-commit`).

---

## Quick Start

Five minutes from a fresh clone to a running service:

```bash
# 1. Clone
git clone https://github.com/your-org/botofarm.git
cd botofarm

# 2. Create an .env file from the example
cp .env.example .env
# Edit .env and set SECRET_KEY to a random string (e.g. openssl rand -hex 32)

# 3. Start the full stack (app + postgres + prometheus + grafana)
make dev

# 4. Verify the service is alive
curl http://localhost:8000/api/v1/health
# {"status":"ok"}

# 5. Open the interactive API docs
open http://localhost:8000/docs
```

---

## Available Commands

All development workflows are driven by `make`. Run `make help` to see the full list.

| Command | Description |
|---------|-------------|
| `make install` | Install runtime + dev dependencies and pre-commit hooks |
| `make dev` | Start the full stack with docker compose |
| `make down` | Stop all containers |
| `make lint` | ruff check + mypy (check only, no changes) |
| `make lint-fix` | ruff check with auto-fix |
| `make format` | ruff format — reformat all Python files |
| `make typecheck` | mypy only |
| `make test` | Unit + API tests (SQLite in-memory, no Docker needed) |
| `make test-watch` | Tests in watch mode |
| `make test-integration` | Lock-path integration tests against real PostgreSQL |
| `make coverage` | Tests with HTML + terminal coverage report |
| `make migrate` | `alembic upgrade head` |
| `make makemigrations MESSAGE="..."` | Generate a new migration |
| `make ci` | Full local CI pipeline: lint → typecheck → test → coverage gate |
| `make build` | Build Docker image locally |
| `make hooks-install` | Install pre-commit hooks |
| `make clean` | Remove `__pycache__`, `.mypy_cache`, `htmlcov`, etc. |

---

## Environment Variables

Copy `.env.example` to `.env` before starting the service locally. In production all variables must be set via your secrets manager (Kubernetes Secrets, GitHub Secrets, etc.).

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://...`) | — | Yes |
| `SECRET_KEY` | Secret used to sign JWT tokens (use `openssl rand -hex 32`) | — | Yes |
| `ALGORITHM` | JWT signing algorithm | `HS256` | No |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime in minutes | `30` | No |
| `LOCK_TTL_SECONDS` | Seconds after which an unreleased lock expires | `300` | No |
| `METRICS_TOKEN` | Bearer token for `/metrics`. Empty = endpoint is open | `""` | No |
| `CORS_ORIGINS` | JSON list of allowed CORS origins | `["http://localhost"]` | No |

Example `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://botofarm:botofarm@db:5432/botofarm
SECRET_KEY=replace-me-with-32-random-bytes
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
LOCK_TTL_SECONDS=300
METRICS_TOKEN=
CORS_ORIGINS=["http://localhost:3000"]
```

---

## API Endpoints

All endpoints under `/api/v1/` (except `/auth/token` and the health probes) require a `Authorization: Bearer <jwt>` header.

### Authentication

**Obtain a JWT token**
```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -F "username=admin@example.com" \
  -F "password=secret123"
# {"access_token":"eyJ...","token_type":"bearer"}
```

### Users

**Create a bot account** `POST /api/v1/users` — returns 201
```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "login": "bot1@example.com",
    "password": "botpassword1",
    "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "env": "stage",
    "domain": "regular"
  }'
```

**List bot accounts** `GET /api/v1/users`
```bash
curl "http://localhost:8000/api/v1/users?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

**Lock (acquire) an account** `POST /api/v1/users/lock` — returns 200 or 404
```bash
curl -X POST http://localhost:8000/api/v1/users/lock \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "env": "stage",
    "domain": "regular"
  }'
```

All filter fields are optional. An empty body `{}` locks the first available account regardless of project/env/domain.

**Release locked accounts** `POST /api/v1/users/free` — returns 200
```bash
# Release all locked accounts across all projects
curl -X POST http://localhost:8000/api/v1/users/free \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Release only accounts for a specific project
curl -X POST http://localhost:8000/api/v1/users/free \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}'
# {"freed": 3}
```

### Health Probes

| Endpoint | Use |
|----------|-----|
| `GET /api/v1/health` | Liveness probe — returns `{"status":"ok"}` if process is alive |
| `GET /api/v1/health/ready` | Readiness probe — checks DB connectivity, returns 503 on failure |
| `GET /api/v1/health/startup` | Startup probe — Kubernetes startup signal |

### Metrics

```bash
# Without METRICS_TOKEN set (open)
curl http://localhost:8000/metrics

# With METRICS_TOKEN=mysecret
curl http://localhost:8000/metrics -H "Authorization: Bearer mysecret"
```

---

## Architecture Overview

```
HTTP request
    │
    ▼
FastAPI (app/main.py)
    │  middleware: CORS, metrics guard
    ▼
API layer  (app/api/v1/)
    │  validates request, calls service
    ▼
Service layer  (app/services/botfarm.py)
    │  business logic, metrics recording, error mapping
    ▼
CRUD layer  (app/crud/user.py)
    │  async SQLAlchemy queries, SELECT FOR UPDATE SKIP LOCKED
    ▼
PostgreSQL 14  (via asyncpg)
```

**Lock/free cycle**

1. `POST /users/lock` — atomically picks the first unlocked (or TTL-expired) row with `SELECT FOR UPDATE SKIP LOCKED`, sets `locktime = now()`.
2. Your test runs using the returned credentials.
3. `POST /users/free` — sets `locktime = NULL` for the project (or globally).
4. Accounts with `locktime < now() - LOCK_TTL_SECONDS` are automatically eligible for re-locking even without an explicit `free` call.

---

## Project Structure

```
.
├── app/
│   ├── api/
│   │   ├── dependencies.py    # JWT auth dependency
│   │   ├── router.py
│   │   └── v1/
│   │       ├── auth.py        # POST /auth/token
│   │       ├── health.py      # GET /health, /health/ready, /health/startup
│   │       └── users.py       # CRUD + lock/free endpoints
│   ├── core/
│   │   ├── config.py          # pydantic-settings — all env vars
│   │   ├── database.py        # async engine, session factory, get_db
│   │   └── security.py        # bcrypt hashing + JWT
│   ├── crud/
│   │   └── user.py            # raw DB operations (no business logic)
│   ├── models/
│   │   └── user.py            # SQLAlchemy ORM model + enums
│   ├── schemas/
│   │   ├── auth.py            # Token schema
│   │   └── user.py            # Request/response Pydantic models
│   ├── services/
│   │   └── botfarm.py         # Business logic orchestration
│   ├── metrics.py             # Custom Prometheus counters/gauges
│   └── main.py                # App factory, middleware, router mount
├── alembic/
│   ├── versions/              # Migration scripts
│   └── env.py
├── tests/
│   ├── conftest.py            # SQLite + Postgres testcontainers fixtures
│   ├── unit/                  # Service-layer unit tests (SQLite)
│   └── api/                   # HTTP-level tests (SQLite + PG for lock path)
├── helm/botofarm/             # Helm chart for minikube / Kubernetes
├── monitoring/
│   ├── prometheus.yml         # Prometheus scrape config
│   └── grafana/               # Datasource + dashboard provisioning
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml             # ruff + mypy + pytest config
├── requirements.txt
└── requirements-dev.txt
```

---

## Testing

Tests are split into two groups:

| Group | Location | Backend | Requires Docker |
|-------|----------|---------|-----------------|
| Unit (service layer) | `tests/unit/` | SQLite in-memory | No |
| API (HTTP routes) | `tests/api/` | SQLite in-memory | No |
| Integration (lock path) | `tests/api/test_lock_pg.py` | Testcontainers PostgreSQL | Yes |

```bash
# Fast tests — no infrastructure needed
make test

# Integration tests — starts a throwaway Postgres container
make test-integration

# All tests with coverage (gate: 75%)
make coverage
```

Coverage reports are written to `htmlcov/index.html` locally and uploaded as a CI artefact on every push.

---

## Monitoring (Prometheus + Grafana)

`make dev` starts Prometheus on port 9090 and Grafana on port 3000.

Custom metrics exposed at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `botofarm_lock_attempts_total` | Counter | Lock attempts labelled by result (`success` / `no_users_available`) |
| `botofarm_lock_operation_duration_seconds` | Histogram | Time taken for each lock operation |
| `botofarm_users_locked_current` | Gauge | Number of currently locked accounts |
| `botofarm_free_users_total` | Counter | Total number of `free` operations |
| `botofarm_users_freed_total` | Counter | Total number of accounts freed |

The Grafana dashboard (`monitoring/grafana/dashboards/botofarm.json`) is provisioned automatically.

- Grafana: http://localhost:3000 — default credentials `admin / admin`
- Prometheus: http://localhost:9090

---

## Deployment

### Docker Compose (local / staging)

```bash
make dev   # builds image, runs migrations, starts all services
make down  # stop
```

### Kubernetes / minikube (Helm)

```bash
# Start minikube
minikube start

# Point Docker CLI at minikube's daemon so the local image is available
eval $(minikube docker-env)
make build

# Deploy
helm upgrade --install botofarm helm/botofarm \
  --set image.tag=local \
  --set secrets.secretKey="$(openssl rand -hex 32)" \
  --set secrets.databaseUrl="postgresql+asyncpg://..."

# Verify
kubectl get pods
kubectl port-forward svc/botofarm 8000:8000
```

### CI/CD

| Trigger | Pipeline |
|---------|---------|
| Any push / PR | `ci.yml` — lint → type-check → test (SQLite) → integration (PG) + coverage gate |
| Push to `main` or a `v*` tag | `docker.yml` — build + push image to GitHub Container Registry |

The Docker image is published to `ghcr.io/<org>/botofarm` and tagged with the branch name, PR number, or semver tag.

---

## Contributing

**Branch naming**
```
feat/<short-description>
fix/<short-description>
chore/<short-description>
```

**Workflow**

1. `make install` on a fresh clone — installs all dependencies and pre-commit hooks.
2. Make your changes. Pre-commit hooks run automatically on `git commit` (ruff lint + format, mypy, secret scanning).
3. `make ci` before pushing — mirrors the full GitHub Actions pipeline locally.
4. Open a PR. CI must be green to merge. No force-pushes to `main`.

**Code review expectations**

- All public functions must have Google-style docstrings and type annotations.
- No business logic in API handlers; no raw queries in the service layer.
- Tests for any new endpoint or service function.
- Coverage must not drop below 75%.
