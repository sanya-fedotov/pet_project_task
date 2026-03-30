"""API tests for /metrics endpoint protection via _guard_metrics middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_metrics_blocked_without_token() -> None:
    """GET /metrics from a non-localhost client with no token returns 403.

    ASGITransport does not set request.client, so the middleware sees an empty
    client host (not 127.0.0.1). With METRICS_TOKEN unset the guard must deny.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_metrics_blocked_with_wrong_token() -> None:
    """GET /metrics with an incorrect bearer token returns 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/metrics",
            headers={"Authorization": "Bearer definitely-wrong-token"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_metrics_allowed_with_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /metrics with the correct bearer token returns 200.

    The METRICS_TOKEN setting is patched in-process so the guard sees a
    non-empty token and accepts the matching Authorization header.
    """
    monkeypatch.setattr(settings, "metrics_token", "test-scrape-token")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/metrics",
            headers={"Authorization": "Bearer test-scrape-token"},
        )
    assert response.status_code == 200
