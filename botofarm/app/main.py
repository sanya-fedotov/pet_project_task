"""FastAPI application factory with lifespan, middleware, and Prometheus metrics."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import default, latency
from sqlalchemy import func, select

from app.api.router import api_router
from app.core.config import settings
from app.core.database import async_session_factory
from app.metrics import BOTOFARM_METRICS_BUCKETS, users_locked_current
from app.models.user import User

_METRICS_PATH = "/metrics"


async def _sync_locked_gauge() -> None:
    """Query the DB for the current count of active locks and seed the gauge.

    Called once at startup so that ``botofarm_users_locked_current`` reflects
    reality after a process restart.  Without this, the gauge starts at zero
    while locked rows may already exist, causing it to go negative the next
    time ``free_users`` decrements it.

    A short-lived session is used so the connection is returned to the pool
    immediately after the count is fetched.
    """
    expiry = datetime.now(timezone.utc) - timedelta(seconds=settings.lock_ttl_seconds)
    stmt = select(func.count()).select_from(User).where(
        User.locktime.is_not(None),
        User.locktime > expiry,
    )
    async with async_session_factory() as session:
        result = await session.execute(stmt)
        count: int = result.scalar_one()
    users_locked_current.set(count)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Runs startup logic before yielding control to the ASGI server and
    teardown logic after the server stops.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the ASGI server while the application is running.
    """
    # Seed the locked-users gauge from the database so that a process restart
    # does not leave the gauge at zero while locks already exist in the DB.
    await _sync_locked_gauge()
    yield


app = FastAPI(
    title="Botofarm",
    description="Bot-farm microservice: manages and leases bot accounts.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — configurable via CORS_ORIGINS env variable
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------------------------------------------------------------------------
# Prometheus metrics — guarded by a static bearer token or localhost-only
# ---------------------------------------------------------------------------
# Use fine-grained buckets covering the full latency spectrum for this
# service: sub-10ms lock contention checks up to 5-second worst-case DB ops.
(
    Instrumentator(excluded_handlers=[_METRICS_PATH])
    .add(
        latency(
            buckets=BOTOFARM_METRICS_BUCKETS,
        )
    )
    .add(default())
    .instrument(app)
    .expose(app, endpoint=_METRICS_PATH, include_in_schema=False)
)

# IMPORTANT: _guard_metrics MUST be registered AFTER Instrumentator().expose().
# Starlette processes @app.middleware("http") decorators in reverse registration
# order (last registered = outermost, runs first). Registering _guard_metrics
# after expose() ensures it wraps the /metrics route and intercepts requests
# before they reach the Prometheus handler. Moving it before expose() would
# cause the guard to be bypassed.


@app.middleware("http")
async def _guard_metrics(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Middleware that restricts access to the /metrics endpoint.

    Requests to ``/metrics`` are allowed only when ``METRICS_TOKEN`` is set
    and the ``Authorization: Bearer <token>`` header matches it exactly.

    All other requests to ``/metrics`` receive a ``403 Forbidden`` response.
    Requests to other paths pass through unchanged.

    Args:
        request: The incoming HTTP request.
        call_next: Callable that forwards the request to the next handler.

    Returns:
        The HTTP response from the next handler, or a 403 if access is denied.
    """
    if request.url.path != _METRICS_PATH:
        return await call_next(request)

    # When METRICS_TOKEN is not configured the endpoint is open — suitable for
    # docker-compose / minikube where Prometheus runs on the same network and
    # network-level access control is sufficient.
    # When METRICS_TOKEN is configured, require a matching Bearer token.
    if not settings.metrics_token:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.metrics_token}"
    if auth_header == expected:
        return await call_next(request)

    return Response(status_code=status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(api_router)
