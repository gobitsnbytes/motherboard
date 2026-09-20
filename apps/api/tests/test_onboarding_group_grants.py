from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Grant, Group
from app.db.seed import (
    DEFAULT_GROUP_GRANTS,
    seed_core_permissions,
    seed_default_group_grants,
    seed_system_groups,
)
from app.iam.policy import can
from app.iam.principal import ResolvedPrincipal


async def test_default_onboarding_grants_are_separated_and_idempotent(
    db_session: AsyncSession,
):
    await seed_system_groups(db_session)
    await seed_core_permissions(db_session)
    await seed_default_group_grants(db_session)
    await seed_default_group_grants(db_session)
    await db_session.commit()

    groups = {
        group.slug: group
        for group in (
            await db_session.execute(
                select(Group).where(
                    Group.slug.in_(("sg_hq", "sg_executive", "sg_department_lead"))
                )
            )
        ).scalars()
    }
    grants = (
        (
            await db_session.execute(
                select(Grant).where(
                    Grant.principal_type == "group",
                    Grant.principal_id.in_([group.id for group in groups.values()]),
                    Grant.permission_key.like("onboarding.%"),
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(grants) == len(DEFAULT_GROUP_GRANTS)

    hq = ResolvedPrincipal(
        user_id=groups["sg_hq"].id,
        group_ids=[groups["sg_hq"].id],
        is_super_admin=False,
    )
    executive = ResolvedPrincipal(
        user_id=groups["sg_executive"].id,
        group_ids=[groups["sg_executive"].id],
        is_super_admin=False,
    )
    department_lead = ResolvedPrincipal(
        user_id=groups["sg_department_lead"].id,
        group_ids=[groups["sg_department_lead"].id],
        is_super_admin=False,
    )

    assert await can(db_session, hq, "onboarding.read")
    assert await can(db_session, hq, "onboarding.write")
    assert not await can(db_session, hq, "onboarding.review")
    assert not await can(db_session, hq, "onboarding.certificate")

    assert await can(db_session, executive, "onboarding.read")
    assert not await can(db_session, executive, "onboarding.write")
    assert await can(db_session, executive, "onboarding.review")
    assert await can(db_session, executive, "onboarding.certificate")

    assert await can(db_session, department_lead, "onboarding.read")
    assert not await can(db_session, department_lead, "onboarding.write")
    assert await can(db_session, department_lead, "onboarding.review")
    assert not await can(db_session, department_lead, "onboarding.certificate")
