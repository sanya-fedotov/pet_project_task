"""Health-check endpoints: startup, liveness, and readiness probes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/startup", summary="Startup probe")
async def startup() -> dict[str, str]:
    """Return a simple startup signal.

    Kubernetes uses this probe to know when the application process has
    finished initialising and is ready to receive liveness/readiness checks.

    Returns:
        ``{"status": "started"}`` once the application is running.
    """
    return {"status": "started"}


@router.get("", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Return a simple liveness signal.

    Returns:
        ``{"status": "ok"}`` if the application process is running.
    """
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Verify that the application can reach the database.

    Args:
        db: Injected async database session.

    Returns:
        ``{"status": "ok"}`` when the database is reachable.

    Raises:
        HTTPException: 503 if the database connection fails.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Database readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not reachable",
        ) from exc
    return {"status": "ok"}
