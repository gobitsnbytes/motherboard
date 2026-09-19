from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.config import get_settings


async def test_cors_allowed_origin(client):
    """Verify that requests from the whitelisted nextauth_url receive CORS headers."""
    settings = get_settings()
    allowed_origin = settings.nextauth_url

    response = await client.get("/health", headers={"Origin": allowed_origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin
    assert response.headers.get("access-control-allow-credentials") == "true"


async def test_cors_disallowed_origin(client):
    """Verify that requests from an untrusted origin do not receive CORS headers."""
    untrusted_origin = "https://evil.com"

    response = await client.get("/health", headers={"Origin": untrusted_origin})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_null_origin(client):
    """Verify that a null origin is not reflected back in CORS headers."""
    response = await client.get("/health", headers={"Origin": "null"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_prefix_bypass_flaw(client):
    """Verify that prefix-match origin bypass attempts (e.g., target.com.evil.com) are rejected."""
    settings = get_settings()
    # E.g., if nextauth_url is http://localhost:3000, try http://localhost:3000.evil.com
    target_clean = settings.nextauth_url.replace("http://", "").replace("https://", "")
    prefix_bypass = f"http://{target_clean}.evil.com"

    response = await client.get("/health", headers={"Origin": prefix_bypass})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_suffix_bypass_flaw(client):
    """Verify that suffix-match origin bypass attempts (e.g., evil-target.com) are rejected."""
    settings = get_settings()
    target_clean = settings.nextauth_url.replace("http://", "").replace("https://", "")
    suffix_bypass = f"http://evil-{target_clean}"

    response = await client.get("/health", headers={"Origin": suffix_bypass})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_preflight_request(client):
    """Verify that preflight OPTIONS requests are handled correctly."""
    settings = get_settings()
    allowed_origin = settings.nextauth_url

    response = await client.options(
        "/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Requested-With",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin
    assert "GET" in response.headers.get("access-control-allow-methods", "")
    assert "access-control-allow-credentials" in response.headers


async def test_cors_origins_env_overrides_nextauth_url(monkeypatch):
    """Verify CORS_ORIGINS supports comma-separated multi-origin deployments."""
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://ops.example.com, https://admin.example.com"
    )
    get_settings.cache_clear()
    # A second app instance built after the env change — the shared `client`
    # fixture is bound to the module-level app and would not see it.
    test_app = create_app()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/health",
                headers={"Origin": "https://admin.example.com"},
            )
            assert response.status_code == 200
            assert (
                response.headers.get("access-control-allow-origin")
                == "https://admin.example.com"
            )

            response = await ac.get(
                "/health",
                headers={"Origin": get_settings().nextauth_url},
            )
            assert response.status_code == 200
            assert "access-control-allow-origin" not in response.headers
    finally:
        get_settings.cache_clear()
