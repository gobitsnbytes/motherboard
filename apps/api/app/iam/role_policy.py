"""Reviewed baseline access, applied only by an operator.

This is not a seed: nothing imports it at startup. An operator runs it by hand,
reads the printed diff, and only then adds `--apply`:

    uv run python -m app.iam.role_policy            # dry run, prints the diff
    uv run python -m app.iam.role_policy --apply    # writes the missing grants + one audit row

It only ever adds grants that are missing and never deletes or edits one, so a
manual revoke stays revoked until someone runs `--apply` again on purpose.

What it grants follows the group descriptions and the approved IAM design:
- HQ and Executive Leadership: operational reads plus fork operations (approve a fork,
  manage its checklist and members). No finance or IAM writes.
- Department Leads: operational reads plus onboarding review. No fork writes.
- Each active fork lead (fork_members.local_role = fork_lead): the fork permissions,
  scoped to `fork:<slug>` for their own fork only, granted to the person.
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Fork, ForkMember, Grant, Group, Permission
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

FORK_OPERATIONS = ("forks.write", "forks.members.write", "onboarding.write")

ROLE_POLICY: dict[str, tuple[str, ...]] = {
    "sg_hq": OPERATIONAL_READS + FORK_OPERATIONS,
    "sg_executive": OPERATIONAL_READS + FORK_OPERATIONS,
    # Reviewing onboarding is the documented reviewer workflow; creators still cannot review their own case.
    "sg_department_lead": OPERATIONAL_READS + ("onboarding.review",),
}

# A fork lead runs their own fork and nothing else: scoped per fork, never global.
FORK_LEAD_PERMISSIONS = (
    "forks.read",
    "forks.write",
    "forks.members.read",
    "forks.members.write",
    "onboarding.read",
    "onboarding.write",
)


@dataclass(frozen=True)
class PlannedGrant:
    principal_type: str  # "group" or "user"
    principal_id: uuid.UUID
    label: str  # group slug or user display name, for the diff only
    permission_key: str
    resource_scope: str | None = None


@dataclass
class Plan:
    missing: list[PlannedGrant]
    unknown_groups: list[str]
    unknown_permissions: list[str]


async def _held(db: AsyncSession, principal_type: str, principal_id: uuid.UUID) -> set:
    rows = await db.execute(
        select(Grant.permission_key, Grant.resource_scope).where(
            Grant.principal_type == principal_type, Grant.principal_id == principal_id
        )
    )
    return {(key, scope) for key, scope in rows.all()}


async def build_plan(db: AsyncSession) -> Plan:
    groups = {g.slug: g for g in (await db.scalars(select(Group).where(Group.slug.in_(ROLE_POLICY)))).all()}
    known = set((await db.scalars(select(Permission.key))).all())
    plan = Plan(missing=[], unknown_groups=[], unknown_permissions=[])

    def want(principal_type, principal_id, label, key, scope, held):
        if key not in known:
            if key not in plan.unknown_permissions:
                plan.unknown_permissions.append(key)
        elif (key, scope) not in held:
            plan.missing.append(PlannedGrant(principal_type, principal_id, label, key, scope))

    for slug, keys in ROLE_POLICY.items():
        group = groups.get(slug)
        if group is None:
            plan.unknown_groups.append(slug)
            continue
        held = await _held(db, "group", group.id)
        for key in keys:
            want("group", group.id, slug, key, None, held)

    leads = (
        await db.execute(
            select(ForkMember.user_id, Fork.slug)
            .join(Fork, Fork.id == ForkMember.fork_id)
            .where(
                ForkMember.local_role == "fork_lead",
                ForkMember.is_active.is_(True),
                Fork.is_active.is_(True),
            )
            .order_by(Fork.slug)
        )
    ).all()
    for user_id, fork_slug in leads:
        held = await _held(db, "user", user_id)
        for key in FORK_LEAD_PERMISSIONS:
            want("user", user_id, f"lead of {fork_slug}", key, f"fork:{fork_slug}", held)
    return plan


async def apply_plan(db: AsyncSession, plan: Plan, actor_id: uuid.UUID | None = None) -> int:
    """Insert the missing grants and one audit row in a single transaction."""
    if not plan.missing:
        return 0
    for item in plan.missing:
        db.add(
            Grant(
                id=uuid.uuid4(),
                principal_type=item.principal_type,
                principal_id=item.principal_id,
                permission_key=item.permission_key,
                resource_scope=item.resource_scope,
                granted_by=actor_id,
            )
        )
    await write_audit_entry(
        db=db,
        actor_id=actor_id,
        action="iam.role_policy.applied",
        target_type="group",
        target_id="access-baseline",
        metadata={
            "grants": [
                f"{m.principal_type}:{m.label}:{m.permission_key}:{m.resource_scope or 'global'}"
                for m in plan.missing
            ]
        },
    )
    await db.commit()
    return len(plan.missing)


def format_plan(plan: Plan) -> str:
    lines = [f"{len(plan.missing)} grant(s) to add:"]
    lines += [
        f"  + {m.label:<28} {m.permission_key:<24} {m.resource_scope or 'global'}" for m in plan.missing
    ]
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
