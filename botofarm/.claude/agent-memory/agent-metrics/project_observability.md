---
name: Botofarm observability architecture
description: Metric naming, alert thresholds, and Grafana layout decisions for Botofarm monitoring
type: project
---

Botofarm uses `prometheus-fastapi-instrumentator` for RED metrics and a custom
`app/metrics.py` module for business metrics.

**Metric prefix:** `botofarm_`

**Histogram buckets** (shared between instrumentator and business histograms):
`(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)` — defined in
`app/metrics.py` as `BOTOFARM_METRICS_BUCKETS`.

**Business metrics** (all in `app/metrics.py`, incremented from `app/services/botfarm.py`):
- `botofarm_lock_attempts_total{result}` — Counter, result: success | no_users_available
- `botofarm_free_users_total` — Counter, each call to free_users endpoint
- `botofarm_users_freed_total` — Counter, sum of freed counts
- `botofarm_users_locked_current` — Gauge, currently locked accounts (inc on lock success, dec on free)
- `botofarm_lock_operation_duration_seconds` — Histogram, SELECT FOR UPDATE duration

**Alert thresholds decided:**
- 5xx error rate > 1% for 2m → critical
- 4xx rate > 10% for 5m → warning (JWT token expiry in CI pipelines)
- P99 latency > 2s for 2m → warning; > 5s → critical
- Pool exhaustion ratio > 20% for 2m → warning; > 50% → critical
- Lock DB op P99 > 1s for 2m → warning (index on users.locktime assumed)

**Grafana dashboard UID:** `botofarm-overview` at `monitoring/grafana/dashboards/botofarm.json`
Dashboard is auto-provisioned via `monitoring/grafana/dashboards/dashboards.yml`.

**Key architectural decision:** `users_locked_current` gauge tracks in-memory
state only — it resets to 0 on restart and does not query the DB. A production
improvement would be a background task that periodically syncs this gauge from
`SELECT COUNT(*) WHERE locktime IS NOT NULL AND locktime >= now() - TTL`.

**Why:** Establishes observability baseline; pool exhaustion is the #1 failure
mode for this service (test suites hang when no bot accounts are available).

**How to apply:** When adding new business operations, follow the pattern in
`app/services/botfarm.py` — instrument at the service layer, never in API
handlers or CRUD.
