.PHONY: help install dev down lint lint-fix format typecheck test test-watch \
        test-integration coverage migrate makemigrations clean hooks-install ci build

# Default target
.DEFAULT_GOAL := help

# ── Variables ──────────────────────────────────────────────────────────────────
PYTHON        := python3
PIP           := $(PYTHON) -m pip
PYTEST        := $(PYTHON) -m pytest
RUFF          := ruff
MYPY          := mypy
COVERAGE_MIN  := 75
SRC           := app
TESTS         := tests

# ── Help ───────────────────────────────────────────────────────────────────────
help:  ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Dependency management ──────────────────────────────────────────────────────
install:  ## Install runtime + dev dependencies and pre-commit hooks
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	$(MAKE) hooks-install

hooks-install:  ## Install pre-commit hooks into .git/hooks
	pre-commit install --install-hooks

# ── Local development ──────────────────────────────────────────────────────────
dev:  ## Start the full stack (app + postgres + prometheus + grafana)
	docker compose up --build -d
	@echo "Service is up."
	@echo "  API:        http://localhost:8000"
	@echo "  Docs:       http://localhost:8000/docs"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3000  (admin / admin)"

down:  ## Stop and remove containers (data volumes are preserved)
	docker compose down

# ── Code quality ───────────────────────────────────────────────────────────────
lint:  ## Run ruff linter and mypy type checker (check-only, no changes)
	$(RUFF) check $(SRC) $(TESTS)
	$(MYPY) $(SRC)/

lint-fix:  ## Run ruff with auto-fix enabled
	$(RUFF) check --fix $(SRC) $(TESTS)

format:  ## Format all Python files with ruff
	$(RUFF) format $(SRC) $(TESTS)

typecheck:  ## Run mypy type checker only
	$(MYPY) $(SRC)/

# ── Testing ────────────────────────────────────────────────────────────────────
test:  ## Run unit + API tests (SQLite in-memory, no Docker needed)
	DATABASE_URL="sqlite+aiosqlite:///:memory:" \
	SECRET_KEY="test-secret-key-for-local-dev" \
	ALGORITHM="HS256" \
	ACCESS_TOKEN_EXPIRE_MINUTES="30" \
	LOCK_TTL_SECONDS="300" \
	METRICS_TOKEN="" \
	CORS_ORIGINS='["http://localhost"]' \
	$(PYTEST) $(TESTS)/unit/ $(TESTS)/api/ -v --tb=short

test-watch:  ## Run tests in watch mode (requires pytest-watch)
	DATABASE_URL="sqlite+aiosqlite:///:memory:" \
	SECRET_KEY="test-secret-key-for-local-dev" \
	ALGORITHM="HS256" \
	ACCESS_TOKEN_EXPIRE_MINUTES="30" \
	LOCK_TTL_SECONDS="300" \
	METRICS_TOKEN="" \
	CORS_ORIGINS='["http://localhost"]' \
	$(PYTHON) -m pytest_watch -- $(TESTS)/unit/ $(TESTS)/api/ -v

test-integration:  ## Run integration tests against a real PostgreSQL (testcontainers)
	DATABASE_URL="sqlite+aiosqlite:///:memory:" \
	SECRET_KEY="test-secret-key-for-local-dev" \
	ALGORITHM="HS256" \
	ACCESS_TOKEN_EXPIRE_MINUTES="30" \
	LOCK_TTL_SECONDS="300" \
	METRICS_TOKEN="" \
	CORS_ORIGINS='["http://localhost"]' \
	$(PYTEST) $(TESTS)/api/test_lock_pg.py -v --tb=short

coverage:  ## Run all tests with coverage report (HTML + terminal)
	DATABASE_URL="sqlite+aiosqlite:///:memory:" \
	SECRET_KEY="test-secret-key-for-local-dev" \
	ALGORITHM="HS256" \
	ACCESS_TOKEN_EXPIRE_MINUTES="30" \
	LOCK_TTL_SECONDS="300" \
	METRICS_TOKEN="" \
	CORS_ORIGINS='["http://localhost"]' \
	$(PYTEST) $(TESTS)/unit/ $(TESTS)/api/ \
		--cov=$(SRC) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=$(COVERAGE_MIN) \
		-v --tb=short
	@echo "HTML coverage report: htmlcov/index.html"

# ── Database migrations ────────────────────────────────────────────────────────
migrate:  ## Apply all pending Alembic migrations (alembic upgrade head)
	alembic upgrade head

makemigrations:  ## Generate a new Alembic migration (set MESSAGE env var for a name)
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make makemigrations MESSAGE='your migration description'"; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(MESSAGE)"

# ── Full CI pipeline (mirrors GitHub Actions) ──────────────────────────────────
ci:  ## Run the full CI pipeline locally: lint → typecheck → test → coverage gate
	@echo "==> [1/4] Linting..."
	$(MAKE) lint
	@echo "==> [2/4] Type checking..."
	$(MAKE) typecheck
	@echo "==> [3/4] Tests..."
	$(MAKE) test
	@echo "==> [4/4] Coverage gate (>= $(COVERAGE_MIN)%)..."
	$(MAKE) coverage
	@echo "All checks passed."

# ── Build ──────────────────────────────────────────────────────────────────────
build:  ## Build the Docker image locally
	docker build -t botofarm:local .

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:  ## Remove Python caches, build artefacts, and coverage reports
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache"   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache"   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov"       -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "Clean."
