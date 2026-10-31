"""Reviewed baseline access for leadership groups, applied only by an operator.

This is not a seed: nothing imports it at startup. An operator runs it by hand,
reads the printed diff, and only then adds `--apply`:

    uv run python -m app.iam.role_policy            # dry run, prints the diff
    uv run python -m app.iam.role_policy --apply    # writes the missing grants + one audit row

It only ever adds grants that are missing and never deletes or edits one, so a
manual revoke stays revoked until someone runs `--apply` again on purpose.
The matrix is the one in docs/superpowers/specs/2026-10-01-iam-rebuild-design.md:
leadership gets operational reads, nobody gets finance or IAM writes from a group.
Fork leads are scoped per fork (`fork:<slug>`) and are assigned in IAM, not here.
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Grant, Group, Permission
from app.iam.audit import write_audit_entry

OPERATIONAL_READS = (
    "iam.users.read",
    "forks.read",
    "forks.members.read",
    "plugins.read",
    "meetings.read",
    "audit.read",
    "onboarding.read",
)

ROLE_POLICY: dict[str, tuple[str, ...]] = {
    "sg_hq": OPERATIONAL_READS,
    "sg_executive": OPERATIONAL_READS,
    # Reviewing onboarding is the documented reviewer workflow; creators still cannot review their own case.
    "sg_department_lead": OPERATIONAL_READS + ("onboarding.review",),
}


@dataclass(frozen=True)
class PlannedGrant:
    group_slug: str
    group_id: uuid.UUID
    permission_key: str


@dataclass
class Plan:
    missing: list[PlannedGrant]
    unknown_groups: list[str]
    unknown_permissions: list[str]


async def build_plan(db: AsyncSession) -> Plan:
    groups = {g.slug: g for g in (await db.scalars(select(Group).where(Group.slug.in_(ROLE_POLICY)))).all()}
    known = set((await db.scalars(select(Permission.key))).all())
    plan = Plan(missing=[], unknown_groups=[], unknown_permissions=[])
    for slug, keys in ROLE_POLICY.items():
        group = groups.get(slug)
        if group is None:
            plan.unknown_groups.append(slug)
            continue
        held = {
            (key, scope)
            for key, scope in (
                await db.execute(
                    select(Grant.permission_key, Grant.resource_scope).where(
                        Grant.principal_type == "group", Grant.principal_id == group.id
                    )
                )
            ).all()
        }
        for key in keys:
            if key not in known:
                if key not in plan.unknown_permissions:
                    plan.unknown_permissions.append(key)
            elif (key, None) not in held:
                plan.missing.append(PlannedGrant(slug, group.id, key))
    return plan


async def apply_plan(db: AsyncSession, plan: Plan, actor_id: uuid.UUID | None = None) -> int:
    """Insert the missing grants and one audit row in a single transaction."""
    if not plan.missing:
        return 0
    for item in plan.missing:
        db.add(
            Grant(
                id=uuid.uuid4(),
                principal_type="group",
                principal_id=item.group_id,
                permission_key=item.permission_key,
                resource_scope=None,
                granted_by=actor_id,
            )
        )
    await write_audit_entry(
        db=db,
        actor_id=actor_id,
        action="iam.role_policy.applied",
        target_type="group",
        target_id="leadership-baseline",
        metadata={"grants": [f"{m.group_slug}:{m.permission_key}" for m in plan.missing]},
    )
    await db.commit()
    return len(plan.missing)


def format_plan(plan: Plan) -> str:
    lines = [f"{len(plan.missing)} grant(s) to add:"]
    lines += [f"  + {m.group_slug:<20} {m.permission_key}" for m in plan.missing]
    lines += [f"  ! group not found: {slug}" for slug in plan.unknown_groups]
    lines += [f"  ! permission not registered: {key}" for key in plan.unknown_permissions]
    return "\n".join(lines)


async def _main(apply: bool) -> int:
    from app.database import get_sessionmaker

    async with get_sessionmaker()() as db:
        plan = await build_plan(db)
        print(format_plan(plan))
        if not apply:
            print("\nDry run. Re-run with --apply to write these grants.")
            return 0
        added = await apply_plan(db, plan)
        print(f"\nApplied {added} grant(s) and wrote one audit entry.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the missing grants (default is a dry run)")
    sys.exit(asyncio.run(_main(parser.parse_args().apply)))
