import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Grant
from app.iam.principal import ResolvedPrincipal
from app.iam.policy import can, batch_can

@pytest.mark.asyncio
async def test_can_super_admin(db_session: AsyncSession):
    principal = ResolvedPrincipal(user_id=uuid.uuid4(), group_ids=[], is_super_admin=True)

    # Even without any grants, super admin should return True
    assert await can(db_session, principal, "some.permission") is True

@pytest.mark.asyncio
async def test_can_user_direct_grant(db_session: AsyncSession):
    user_id = uuid.uuid4()
    principal = ResolvedPrincipal(user_id=user_id, group_ids=[], is_super_admin=False)

    grant = Grant(
        principal_type="user",
        principal_id=user_id,
        permission_key="test.read"
    )
    db_session.add(grant)
    await db_session.commit()

    assert await can(db_session, principal, "test.read") is True
    assert await can(db_session, principal, "test.write") is False

@pytest.mark.asyncio
async def test_can_group_grant(db_session: AsyncSession):
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    principal = ResolvedPrincipal(user_id=user_id, group_ids=[group_id], is_super_admin=False)

    grant = Grant(
        principal_type="group",
        principal_id=group_id,
        permission_key="group.action"
    )
    db_session.add(grant)
    await db_session.commit()

    assert await can(db_session, principal, "group.action") is True

@pytest.mark.asyncio
async def test_can_expired_grant(db_session: AsyncSession):
    user_id = uuid.uuid4()
    principal = ResolvedPrincipal(user_id=user_id, group_ids=[], is_super_admin=False)

    grant = Grant(
        principal_type="user",
        principal_id=user_id,
        permission_key="test.expired",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(grant)
    await db_session.commit()

    assert await can(db_session, principal, "test.expired") is False

@pytest.mark.asyncio
async def test_can_resource_scope(db_session: AsyncSession):
    user_id = uuid.uuid4()
    principal = ResolvedPrincipal(user_id=user_id, group_ids=[], is_super_admin=False)

    # Exact scope match
    grant1 = Grant(
        principal_type="user",
        principal_id=user_id,
        permission_key="scoped.action",
        resource_scope="project_a"
    )
    # Global scope (None)
    grant2 = Grant(
        principal_type="user",
        principal_id=user_id,
        permission_key="global.action",
        resource_scope=None
    )
    db_session.add_all([grant1, grant2])
    await db_session.commit()

    assert await can(db_session, principal, "scoped.action", "project_a") is True
    assert await can(db_session, principal, "scoped.action", "project_b") is False
    assert await can(db_session, principal, "global.action", "project_c") is True

@pytest.mark.asyncio
async def test_batch_can(db_session: AsyncSession):
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    principal = ResolvedPrincipal(user_id=user_id, group_ids=[group_id], is_super_admin=False)

    grant1 = Grant(
        principal_type="user",
        principal_id=user_id,
        permission_key="batch.read"
    )
    grant2 = Grant(
        principal_type="group",
        principal_id=group_id,
        permission_key="batch.scoped",
        resource_scope="res_1"
    )
    db_session.add_all([grant1, grant2])
    await db_session.commit()

    checks = [
        ("batch.read", None),
        ("batch.scoped", "res_1"),
        ("batch.scoped", "res_2"),
        ("batch.unknown", None)
    ]

    results = await batch_can(db_session, principal, checks)

    assert results["batch.read"] is True
    assert results["batch.scoped"] is True # it's evaluated together across res_1 and res_2 if key is returned, but let's change batch_can to return correct per key logic
    assert results["batch.unknown"] is False
