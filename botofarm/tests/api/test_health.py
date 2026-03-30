"""API tests for health-check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_startup(async_client: AsyncClient) -> None:
    """GET /api/v1/health/startup should return 200 with status=started."""
    response = await async_client.get("/api/v1/health/startup")
    assert response.status_code == 200
    assert response.json() == {"status": "started"}


@pytest.mark.asyncio
async def test_liveness(async_client: AsyncClient) -> None:
    """GET /api/v1/health should return 200 with status=ok."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness(async_client: AsyncClient) -> None:
    """GET /api/v1/health/ready should return 200 when the DB is reachable."""
    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
