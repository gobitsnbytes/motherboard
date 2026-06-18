import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import get_settings


@pytest.mark.asyncio
async def test_cors_allowed_origin():
    """Verify that requests from the whitelisted nextauth_url receive CORS headers."""
    settings = get_settings()
    allowed_origin = settings.nextauth_url

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/health/",
            headers={"Origin": allowed_origin}
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == allowed_origin
        assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_disallowed_origin():
    """Verify that requests from an untrusted origin do not receive CORS headers."""
    untrusted_origin = "https://evil.com"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/health/",
            headers={"Origin": untrusted_origin}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_null_origin():
    """Verify that a null origin is not reflected back in CORS headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/health/",
            headers={"Origin": "null"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_prefix_bypass_flaw():
    """Verify that prefix-match origin bypass attempts (e.g., target.com.evil.com) are rejected."""
    settings = get_settings()
    # E.g., if nextauth_url is http://localhost:3000, try http://localhost:3000.evil.com
    target_clean = settings.nextauth_url.replace("http://", "").replace("https://", "")
    prefix_bypass = f"http://{target_clean}.evil.com"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/health/",
            headers={"Origin": prefix_bypass}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_suffix_bypass_flaw():
    """Verify that suffix-match origin bypass attempts (e.g., evil-target.com) are rejected."""
    settings = get_settings()
    target_clean = settings.nextauth_url.replace("http://", "").replace("https://", "")
    suffix_bypass = f"http://evil-{target_clean}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/health/",
            headers={"Origin": suffix_bypass}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_preflight_request():
    """Verify that preflight OPTIONS requests are handled correctly."""
    settings = get_settings()
    allowed_origin = settings.nextauth_url

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.options(
            "/health/",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Requested-With",
            }
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == allowed_origin
        assert "GET" in response.headers.get("access-control-allow-methods", "")
        assert "access-control-allow-credentials" in response.headers
