"""API tests for health-check endpoints.

Covers:
- GET /api/v1/health/startup — startup probe
- GET /api/v1/health          — liveness probe
- GET /api/v1/health/ready   — readiness probe (hits the DB)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError


@pytest.mark.asyncio
async def test_startup_returns_200_with_started_status(
    async_client: AsyncClient,
) -> None:
    """GET /api/v1/health/startup returns 200 with status=started."""
    response = await async_client.get("/api/v1/health/startup")

    assert response.status_code == 200
    assert response.json() == {"status": "started"}


@pytest.mark.asyncio
async def test_liveness_returns_200_with_ok_status(
    async_client: AsyncClient,
) -> None:
    """GET /api/v1/health returns 200 with status=ok."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_returns_200_when_db_is_reachable(
    async_client: AsyncClient,
) -> None:
    """GET /api/v1/health/ready returns 200 when the DB responds."""
    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_returns_503_when_db_is_unreachable(
    async_client: AsyncClient,
) -> None:
    """GET /api/v1/health/ready returns 503 when the database is unreachable.

    We patch ``AsyncSession.execute`` so it raises ``OperationalError``,
    simulating a DB outage without needing to tear down the actual connection.
    """
    with patch(
        "app.api.v1.health.AsyncSession.execute",
        new_callable=AsyncMock,
        side_effect=OperationalError("connect", None, Exception("timeout")),
    ):
        response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert "not reachable" in response.json()["detail"].lower()
