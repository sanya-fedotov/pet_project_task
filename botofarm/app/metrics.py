"""Prometheus metrics registry for Botofarm.

All application-level metrics are defined here as module-level singletons so
they are registered exactly once with the default Prometheus registry.  Import
and increment/observe them from the service layer — never from API handlers or
CRUD functions directly.

Metric naming convention: ``botofarm_<noun>_<unit_or_total>``.
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Histogram buckets — shared with prometheus_fastapi_instrumentator so that
# the RED duration metric uses the same resolution as business histograms.
# Covers sub-10 ms DB fast-path up to 5-second worst-case lock contention.
# ---------------------------------------------------------------------------
BOTOFARM_METRICS_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
)

# ---------------------------------------------------------------------------
# Lock / free — core business operations of the bot farm
# ---------------------------------------------------------------------------

lock_attempts_total = Counter(
    "botofarm_lock_attempts_total",
    "Total number of lock_user attempts.",
    ["result"],  # result: "success" | "no_users_available"
)
"""Counts every call to ``POST /api/v1/users/lock``.

Label ``result`` distinguishes successful acquisitions from 404s so that the
ratio ``botofarm_lock_attempts_total{result="no_users_available"} /
botofarm_lock_attempts_total`` expresses pool exhaustion rate.
"""

free_users_total = Counter(
    "botofarm_free_users_total",
    "Total number of free_users calls.",
)
"""Counts every call to ``POST /api/v1/users/free``."""

users_freed_total = Counter(
    "botofarm_users_freed_total",
    "Total number of individual user accounts released by free_users calls.",
)
"""Counts the sum of all ``freed`` values returned by free_users.

Use this alongside ``free_users_total`` to compute the average batch size per
free call.
"""

# ---------------------------------------------------------------------------
# Pool state — current snapshot of the bot account pool
# ---------------------------------------------------------------------------

users_locked_current = Gauge(
    "botofarm_users_locked_current",
    "Number of bot accounts currently locked (locktime IS NOT NULL and not expired).",
)
"""Gauge updated on every lock and free operation.

A sustained increase toward the total pool size means the pool is about to be
exhausted — alert before it hits 100 %.
"""

# ---------------------------------------------------------------------------
# Lock duration — how long each acquired account stays locked before freed
# (approximated from the service layer; exact TTL tracking needs a background
# job, so this measures the operation round-trip time instead)
# ---------------------------------------------------------------------------

lock_operation_duration_seconds = Histogram(
    "botofarm_lock_operation_duration_seconds",
    "Duration of the lock_user database operation (SELECT FOR UPDATE).",
    buckets=BOTOFARM_METRICS_BUCKETS,
)
"""Tracks how long the atomic lock acquisition takes in the database.

P99 spikes here indicate lock contention or slow index scans on the
``locktime`` column.
"""
