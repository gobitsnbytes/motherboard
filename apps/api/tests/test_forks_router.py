import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import Fork, ForkMember, User
from app.db.seeder import run_seeds
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_forks(db_session: AsyncSession, super_admin: User):
    # Run the seeder to populate default forks
    await run_seeds(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, super_admin.id, "GET", "/api/forks/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 4  # Delhi, Bangalore, Hyderabad, Kolkata
        slugs = [f["slug"] for f in data]
        assert "delhi" in slugs


@pytest.mark.asyncio
async def test_get_fork(db_session: AsyncSession, super_admin: User):
    fork = Fork(slug="test-fork-get", city_name="Test Fork City", metadata_json={})
    db_session.add(fork)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Happy path
        response = await request_as(ac, super_admin.id, "GET", f"/api/forks/{fork.id}")
        assert response.status_code == 200
        assert response.json()["city_name"] == "Test Fork City"

        # 404
        response = await request_as(ac, super_admin.id, "GET", f"/api/forks/{uuid.uuid4()}")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_fork(db_session: AsyncSession, super_admin: User):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "slug": "chennai",
            "city_name": "Chennai Fork",
            "discord_city_role_id": "role_chennai",
            "discord_contributor_role_id": "role_chennai_contrib",
            "is_active": True,
            "metadata_json": {"population": "10m"}
        }
        response = await request_as(ac, super_admin.id, "POST", "/api/forks/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "chennai"
        assert data["city_name"] == "Chennai Fork"
        assert data["metadata_json"] == {"population": "10m"}


@pytest.mark.asyncio
async def test_update_fork(db_session: AsyncSession, super_admin: User):
    fork = Fork(slug="pune", city_name="Pune Fork", metadata_json={})
    db_session.add(fork)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "city_name": "Pune City Fork",
            "is_active": False,
            "metadata_json": {"weather": "nice"}
        }
        response = await request_as(ac, super_admin.id, "PATCH", f"/api/forks/{fork.id}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["city_name"] == "Pune City Fork"
        assert data["is_active"] is False
        assert data["metadata_json"] == {"weather": "nice"}


@pytest.mark.asyncio
async def test_list_fork_members(db_session: AsyncSession, super_admin: User):
    fork = Fork(slug="mumbai", city_name="Mumbai Fork", metadata_json={})
    user = User(display_name="Mumbai Member")
    db_session.add_all([fork, user])
    await db_session.commit()

    member = ForkMember(
        user_id=user.id,
        fork_id=fork.id,
        track="education",
        local_role="fork_lead",
        is_active=True
    )
    db_session.add(member)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, super_admin.id, "GET", f"/api/forks/{fork.id}/members")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == str(user.id)
        assert data[0]["track"] == "education"
        assert data[0]["local_role"] == "fork_lead"
        assert data[0]["is_active"] is True
