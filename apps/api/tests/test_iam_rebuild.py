from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import (
    AuditLog,
    Fork,
    ForkMember,
    Grant,
    Group,
    Membership,
    Permission,
    User,
)
from app.iam.access import require_delegable
from app.iam.fork_access import allowed_fork_ids, require_fork_access
from app.iam.policy import batch_can, can
from app.iam.principal import resolve_principal
from conftest import request_as


async def test_scoped_batch_does_not_become_global(db_session):
    user = User(display_name="Lead")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Grant(
            principal_type="user",
            principal_id=user.id,
            permission_key="onboarding.write",
            resource_scope="fork:nagpur",
        )
    )
    await db_session.commit()
    principal = await resolve_principal(db_session, user.id)
    requests = [
        ("onboarding.write", None),
        ("onboarding.write", "fork:nagpur"),
        ("onboarding.write", "fork:noida"),
    ]
    assert await batch_can(db_session, principal, requests) == dict(
        zip(requests, [False, True, False])
    )
    assert [await can(db_session, principal, *item) for item in requests] == [
        False,
        True,
        False,
    ]


async def test_delegation_cannot_outlive_group_membership(db_session):
    user = User(display_name="Temporary admin")
    group = Group(name="Temporary", slug="temporary")
    db_session.add_all([user, group])
    await db_session.flush()
    db_session.add_all(
        [
            Membership(
                user_id=user.id,
                group_id=group.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
            Grant(
                principal_type="group",
                principal_id=group.id,
                permission_key="forks.read",
            ),
        ]
    )
    await db_session.commit()
    principal = await resolve_principal(db_session, user.id)
    with pytest.raises(HTTPException) as error:
        await require_delegable(db_session, principal, "forks.read", None)
    assert error.value.status_code == 403
    await require_delegable(
        db_session,
        principal,
        "forks.read",
        None,
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )


async def test_scope_needs_assignment_and_never_crosses_forks(db_session):
    user = User(display_name="Nagpur lead")
    nagpur = Fork(slug="nagpur", city_name="Nagpur")
    noida = Fork(slug="noida", city_name="Noida")
    db_session.add_all([user, nagpur, noida])
    await db_session.flush()
    db_session.add(
        Grant(
            principal_type="user",
            principal_id=user.id,
            permission_key="onboarding.write",
            resource_scope="fork:nagpur",
        )
    )
    await db_session.commit()
    principal = await resolve_principal(db_session, user.id)
    assert await allowed_fork_ids(db_session, principal, "onboarding.write") == []
    db_session.add(
        ForkMember(user_id=user.id, fork_id=nagpur.id, local_role="fork_lead")
    )
    await db_session.commit()
    assert await allowed_fork_ids(db_session, principal, "onboarding.write") == [
        nagpur.id
    ]
    await require_fork_access(db_session, principal, "onboarding.write", nagpur.id)
    with pytest.raises(HTTPException) as error:
        await require_fork_access(db_session, principal, "onboarding.write", noida.id)
    assert error.value.status_code == 403


async def test_policy_revision_and_before_after_audit(db_session, client, super_admin):
    group = Group(name="Explicit", slug="explicit")
    db_session.add_all([group, Permission(key="forks.read")])
    await db_session.commit()
    path = f"/api/iam/groups/{group.id}/policy"
    before = (await request_as(client, super_admin.id, "GET", path)).json()
    payload = {
        "expected_revision": before["revision"],
        "grants": [{"permission_key": "forks.read"}],
    }
    response = await request_as(client, super_admin.id, "PUT", path, json=payload)
    assert response.status_code == 200
    stale = await request_as(client, super_admin.id, "PUT", path, json=payload)
    assert stale.status_code == 409
    log = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "iam.group_policy.updated")
    )
    assert log is not None
    assert (
        len(
            (
                await db_session.scalars(
                    select(Grant).where(Grant.principal_id == group.id)
                )
            ).all()
        )
        == 1
    )


async def test_iam_editor_cannot_grant_authority_they_do_not_hold(db_session, client):
    user = User(display_name="Restricted IAM editor")
    target = User(display_name="Target")
    db_session.add_all([user, target, Permission(key="finance.ledger.read")])
    await db_session.flush()
    db_session.add(
        Grant(
            principal_type="user",
            principal_id=user.id,
            permission_key="iam.grants.write",
        )
    )
    await db_session.commit()
    response = await request_as(
        client,
        user.id,
        "POST",
        "/api/iam/grants",
        json={
            "principal_type": "user",
            "principal_id": str(target.id),
            "permission_key": "finance.ledger.read",
        },
    )
    assert response.status_code == 403
    assert (
        await db_session.scalar(select(Grant).where(Grant.principal_id == target.id))
        is None
    )
