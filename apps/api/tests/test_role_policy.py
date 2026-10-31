from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Grant, Group
from app.iam.policy import can
from app.iam.principal import ResolvedPrincipal
from app.iam.role_policy import ROLE_POLICY, apply_plan, build_plan, format_plan
from seed_fixtures import seed_core_permissions, seed_system_groups


async def _setup(db: AsyncSession) -> None:
    await seed_system_groups(db)
    await seed_core_permissions(db)
    await db.commit()


async def test_dry_run_lists_every_grant_and_writes_nothing(db_session: AsyncSession):
    await _setup(db_session)
    plan = await build_plan(db_session)
    assert len(plan.missing) == sum(len(v) for v in ROLE_POLICY.values())
    assert not plan.unknown_groups and not plan.unknown_permissions
    assert "+ sg_hq" in format_plan(plan)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "iam.role_policy.applied")
        )
        == 0
    )


async def test_apply_grants_reads_only_and_is_idempotent(db_session: AsyncSession):
    await _setup(db_session)
    first = await apply_plan(db_session, await build_plan(db_session))
    assert first > 0
    assert await apply_plan(db_session, await build_plan(db_session)) == 0

    hq = (await db_session.scalars(select(Group).where(Group.slug == "sg_hq"))).one()
    lead = (
        await db_session.scalars(
            select(Group).where(Group.slug == "sg_department_lead")
        )
    ).one()
    as_hq = ResolvedPrincipal(user_id=hq.id, group_ids=[hq.id], is_super_admin=False)
    as_lead = ResolvedPrincipal(
        user_id=lead.id, group_ids=[lead.id], is_super_admin=False
    )

    assert await can(db_session, as_hq, "audit.read")
    assert await can(db_session, as_lead, "onboarding.review")
    # The boundary from the design: no finance or IAM writes come from a leadership group.
    for key in (
        "finance.requests.approve",
        "iam.grants.write",
        "iam.users.write",
        "finance.admin",
    ):
        assert not await can(db_session, as_hq, key)
        assert not await can(db_session, as_lead, key)
    assert not await can(db_session, as_hq, "onboarding.review")


async def test_a_revoked_grant_stays_revoked_until_apply_is_run_again(
    db_session: AsyncSession,
):
    await _setup(db_session)
    await apply_plan(db_session, await build_plan(db_session))
    hq = (await db_session.scalars(select(Group).where(Group.slug == "sg_hq"))).one()
    grant = (
        await db_session.scalars(
            select(Grant).where(
                Grant.principal_id == hq.id, Grant.permission_key == "audit.read"
            )
        )
    ).one()
    await db_session.delete(grant)
    await db_session.commit()
    # Merely building the plan (what a deploy or startup could do) changes nothing.
    plan = await build_plan(db_session)
    assert [(m.group_slug, m.permission_key) for m in plan.missing] == [
        ("sg_hq", "audit.read")
    ]
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Grant)
            .where(Grant.principal_id == hq.id, Grant.permission_key == "audit.read")
        )
        == 0
    )
