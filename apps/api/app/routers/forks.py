"""Forks router — city fork management, member listing, onboarding pipeline, and compliance checks."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import Fork, ForkMember, User
from app.dependencies import CurrentUserDep, DbSession
from app.iam.audit import write_audit_entry
from app.iam.policy import require_permission
from app.schemas.forks import (
    ComplianceCheckItem,
    ForkComplianceCheckOut,
    ForkCreate,
    ForkMemberCreate,
    ForkMemberOut,
    ForkOnboardingDetailOut,
    ForkOnboardingItem,
    ForkOut,
    ForkStageActionPayload,
    ForkUpdate,
    OnboardingChecklistStepOut,
    OnboardingStepUpdate,
)

router = APIRouter(prefix="/api/forks", tags=["forks"])

# 7-step onboarding journey defined in the Network Governance Charter / IOM (§4.1).
ONBOARDING_STEPS: list[dict[str, str]] = [
    {"key": "github_invite", "label": "Accept GitHub organization invite"},
    {"key": "leads_discord", "label": "Join the Leads Discord server"},
    {"key": "email_setup", "label": "Set up [city]@gobitsnbytes.org email"},
    {"key": "website_deploy", "label": "Deploy the local landing page"},
    {"key": "notion_share", "label": "Share local Notion workspace with Upstream"},
    {"key": "first_pulse", "label": "Submit first /pulse activity entry"},
    {"key": "team_event_plan", "label": "Define core team & plan first event"},
]

# Stage progression: which steps must be complete to leave each stage.
STAGE_EXIT_REQUIREMENTS: dict[str, list[str]] = {
    "submitted": ["github_invite", "leads_discord"],
    "in_review": ["email_setup", "website_deploy", "notion_share"],
    # Approved additionally requires full compliance (checked at runtime).
    "compliance_check": [
        "github_invite",
        "leads_discord",
        "email_setup",
        "website_deploy",
        "notion_share",
        "first_pulse",
        "team_event_plan",
    ],
}
STAGE_ORDER = ["submitted", "in_review", "compliance_check", "approved"]


def _get_checklist(fork: Fork) -> list[OnboardingChecklistStepOut]:
    saved = (fork.metadata_json or {}).get("onboarding_checklist", {})
    steps: list[OnboardingChecklistStepOut] = []
    for step in ONBOARDING_STEPS:
        state = saved.get(step["key"], {}) if isinstance(saved, dict) else {}
        steps.append(
            OnboardingChecklistStepOut(
                key=step["key"],
                label=step["label"],
                completed=bool(state.get("completed")),
                completed_at=state.get("completed_at"),
                completed_by=state.get("completed_by"),
            )
        )
    return steps


def evaluate_fork_compliance(fork: Fork, members: list[ForkMember]) -> ForkComplianceCheckOut:
    metadata = fork.metadata_json or {}
    active_members = [m for m in members if m.is_active]

    # 1. Statutory Non-Profit Section 8 Alignment Check
    s8_val = metadata.get("section8_aligned")
    if s8_val is None:
        s8_val = metadata.get("section_8_aligned")
    if s8_val is None:
        s8_val = metadata.get("section_8_compliance", True)
    s8_passed = bool(s8_val)

    check_s8 = ComplianceCheckItem(
        key="section8_alignment",
        title="Statutory Non-Profit Section 8 Alignment",
        passed=s8_passed,
        status="passed" if s8_passed else "failed",
        details="Fork operates under GOBITSNBYTES FOUNDATION Section 8 non-profit charter."
        if s8_passed
        else "Fork metadata indicates non-alignment with MCA Section 8 non-profit charter.",
        remedy=None
        if s8_passed
        else "Re-align local fork charter with Upstream Section 8 non-profit statutory guidelines.",
    )

    # 2. Fork Recognition Agreement Signature Check
    agreement_val = metadata.get("agreement_signed")
    if agreement_val is None:
        agreement_val = metadata.get("recognition_agreement_signed")
    if agreement_val is None:
        agreement_val = metadata.get("fork_agreement_status") == "signed"
    agreement_passed = bool(agreement_val)

    check_agreement = ComplianceCheckItem(
        key="agreement_signed",
        title="Fork Recognition Agreement Signature",
        passed=agreement_passed,
        status="passed" if agreement_passed else "failed",
        details="Fork Recognition Agreement executed and signed by designated lead."
        if agreement_passed
        else "Fork Recognition Agreement is missing or pending signature.",
        remedy=None
        if agreement_passed
        else "Execute and upload signed Fork Recognition Agreement via Contract Assistant.",
    )

    # 3. Minor Safeguarding Consent Protocol (POCSO & DPDP Act 2023)
    safeguard_val = metadata.get("safeguarding_compliant")
    if safeguard_val is None:
        safeguard_val = metadata.get("pocso_dpdp_compliant")
    if safeguard_val is None:
        safeguard_val = metadata.get("parental_consent_verified", False)
    safeguarding_passed = bool(safeguard_val)

    check_safeguarding = ComplianceCheckItem(
        key="minor_safeguarding",
        title="Minor Safeguarding Consent Protocol (POCSO & DPDP Act 2023)",
        passed=safeguarding_passed,
        status="passed" if safeguarding_passed else "failed",
        details="Parental consent & minor safeguarding verified under POCSO 2012 and DPDP Act 2023."
        if safeguarding_passed
        else "Parental consent audit pending or Form No. 2 verification missing.",
        remedy=None
        if safeguarding_passed
        else "Collect and verify signed Parental/Guardian Consent Forms (Form No. 2) for all minor organizers.",
    )

    # 4. Mandatory Track Lead Roles Assigned
    required_tracks = ["tech", "creative", "ops", "outreach"]
    assigned_leads: dict[str, str | None] = {t: None for t in required_tracks}

    for m in active_members:
        role = (m.local_role or "").lower()
        track = (m.track or "").lower()
        if "lead" in role or role == "fork_lead":
            if track in assigned_leads and not assigned_leads[track]:
                assigned_leads[track] = str(m.user_id)
        if ("tech" in role or role == "tech-lead") and not assigned_leads["tech"]:
            assigned_leads["tech"] = str(m.user_id)
        elif ("creative" in role or role == "creative-lead") and not assigned_leads["creative"]:
            assigned_leads["creative"] = str(m.user_id)
        elif ("ops" in role or role == "ops-lead") and not assigned_leads["ops"]:
            assigned_leads["ops"] = str(m.user_id)
        elif ("outreach" in role or role == "outreach-lead") and not assigned_leads["outreach"]:
            assigned_leads["outreach"] = str(m.user_id)

    meta_leads = metadata.get("track_leads") or metadata.get("assigned_roles") or {}
    if isinstance(meta_leads, dict):
        for t in required_tracks:
            if not assigned_leads[t] and meta_leads.get(t):
                assigned_leads[t] = str(meta_leads.get(t))

    missing_tracks = [t for t, lead in assigned_leads.items() if not lead]
    track_leads_passed = len(missing_tracks) == 0

    check_track_leads = ComplianceCheckItem(
        key="track_leads_assigned",
        title="Mandatory Track Lead Roles Assigned",
        passed=track_leads_passed,
        status="passed" if track_leads_passed else "failed",
        details="All 4 mandatory track leads assigned (tech, creative, ops, outreach)."
        if track_leads_passed
        else f"Missing track lead roles: {', '.join(missing_tracks)}.",
        remedy=None
        if track_leads_passed
        else f"Appoint and register track leads for missing tracks: {', '.join(missing_tracks)}.",
    )

    # 5. Financial Isolation Rule
    has_local_bank = metadata.get("has_local_bank_account", False) or metadata.get("local_bank_account", False)
    explicit_isolation = metadata.get("financial_isolation")
    if explicit_isolation is None:
        explicit_isolation = metadata.get("financial_isolation_compliant")

    if has_local_bank or explicit_isolation is False:
        fin_passed = False
    else:
        fin_passed = True

    check_financial = ComplianceCheckItem(
        key="financial_isolation",
        title="Financial Isolation Rule",
        passed=fin_passed,
        status="passed" if fin_passed else "failed",
        details="Financial isolation active: No local bank accounts, all sponsorships routed upstream via RazorpayX."
        if fin_passed
        else "Violation: Unauthorized local bank account or direct payment routing detected.",
        remedy=None
        if fin_passed
        else "Close local bank/UPI accounts immediately and route all sponsorship & financial grants through Upstream RazorpayX treasury.",
    )

    # 6. 0-100 Fork Health Score Algorithm
    check_points = sum(
        12 for c in [check_s8, check_agreement, check_safeguarding, check_track_leads, check_financial] if c.passed
    )
    track_points = (4 - len(missing_tracks)) * 5
    member_points = min(20, len(active_members) * 5)

    total_health_score = min(100, max(0, check_points + track_points + member_points))
    health_passed = total_health_score >= 70
    health_status = "passed" if total_health_score >= 70 else ("warning" if total_health_score >= 40 else "failed")

    check_health = ComplianceCheckItem(
        key="health_score_eval",
        title="0-100 Fork Health Score Algorithm",
        passed=health_passed,
        status=health_status,
        details=f"Calculated Fork Health Score: {total_health_score}/100.",
        remedy=None
        if health_passed
        else f"Fork health score is below threshold ({total_health_score}/100). Resolve pending compliance remedies to improve score.",
    )

    all_checks = [check_s8, check_agreement, check_safeguarding, check_track_leads, check_financial, check_health]
    passed_count = sum(1 for c in all_checks if c.passed)

    if passed_count == len(all_checks):
        overall_status = "compliant"
    elif passed_count >= 4:
        overall_status = "warning"
    else:
        overall_status = "non_compliant"

    return ForkComplianceCheckOut(
        fork_id=fork.id,
        city_name=fork.city_name,
        slug=fork.slug,
        health_score=total_health_score,
        overall_status=overall_status,
        passed_checks_count=passed_count,
        total_checks_count=len(all_checks),
        checks=all_checks,
        assigned_track_leads=assigned_leads,
        created_at=fork.created_at,
        updated_at=fork.updated_at,
    )


@router.get("/", response_model=list[ForkOut])
async def list_forks(db: DbSession, current_user: CurrentUserDep) -> list[Fork]:
    await require_permission(db, current_user, "forks.read")
    result = await db.execute(select(Fork).order_by(Fork.city_name))
    return list(result.scalars().all())


@router.get("/onboarding", response_model=list[ForkOnboardingItem])
async def list_forks_onboarding(
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[ForkOnboardingItem]:
    await require_permission(db, current_user, "forks.read")
    forks_result = await db.execute(select(Fork).order_by(Fork.city_name))
    forks = list(forks_result.scalars().all())

    onboarding_items: list[ForkOnboardingItem] = []
    for fork in forks:
        members_result = await db.execute(
            select(ForkMember).where(ForkMember.fork_id == fork.id, ForkMember.is_active.is_(True))
        )
        members = list(members_result.scalars().all())

        compliance = evaluate_fork_compliance(fork, members)
        stage = _current_stage(fork, compliance)

        assigned_track_count = sum(1 for lead in compliance.assigned_track_leads.values() if lead)
        remedies = [check.remedy for check in compliance.checks if check.remedy]

        onboarding_items.append(
            ForkOnboardingItem(
                fork_id=fork.id,
                city_name=fork.city_name,
                slug=fork.slug,
                stage=stage,
                is_active=fork.is_active,
                health_score=compliance.health_score,
                compliance_summary=compliance,
                track_leads_assigned_count=assigned_track_count,
                member_count=len(members),
                remedies_needed=remedies,
            )
        )

    return onboarding_items


@router.get("/{fork_id}", response_model=ForkOut)
async def get_fork(
    fork_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> Fork:
    await require_permission(db, current_user, "forks.read")
    fork = await db.get(Fork, fork_id)
    if not fork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork not found.")
    return fork


@router.get("/{fork_id}/compliance-check", response_model=ForkComplianceCheckOut)
async def get_fork_compliance_check(
    fork_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> ForkComplianceCheckOut:
    await require_permission(db, current_user, "forks.read")
    fork = await db.get(Fork, fork_id)
    if not fork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork not found.")

    members_result = await db.execute(
        select(ForkMember).where(ForkMember.fork_id == fork.id, ForkMember.is_active.is_(True))
    )
    members = list(members_result.scalars().all())

    return evaluate_fork_compliance(fork, members)


@router.post("/", response_model=ForkOut, status_code=status.HTTP_201_CREATED)
async def create_fork(
    payload: ForkCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Fork:
    await require_permission(db, current_user, "forks.write")
    fork = Fork(**payload.model_dump())
    db.add(fork)
    await db.commit()
    await db.refresh(fork)
    return fork


@router.patch("/{fork_id}", response_model=ForkOut)
async def update_fork(
    fork_id: Annotated[uuid.UUID, ...],
    payload: ForkUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Fork:
    await require_permission(db, current_user, "forks.write")
    fork = await db.get(Fork, fork_id)
    if not fork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fork, field, value)
    await db.commit()
    await db.refresh(fork)
    return fork


@router.get("/{fork_id}/members", response_model=list[ForkMemberOut])
async def list_fork_members(
    fork_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[ForkMember]:
    await require_permission(db, current_user, "forks.members.read")
    result = await db.execute(
        select(ForkMember).where(ForkMember.fork_id == fork_id, ForkMember.is_active.is_(True))
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Onboarding pipeline (write surface)
# ---------------------------------------------------------------------------


async def _load_fork_or_404(db, fork_id: uuid.UUID) -> Fork:
    # Always SELECT fresh: bulk updates elsewhere can leave identity-map
    # instances expired, and db.get() would return them without repopulating.
    result = await db.execute(select(Fork).where(Fork.id == fork_id))
    fork = result.scalar_one_or_none()
    if not fork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork not found.")
    return fork


def _current_stage(fork: Fork, compliance: ForkComplianceCheckOut) -> str:
    """Resolve the effective onboarding stage.

    Stage resolution order:
    1. Explicit ``onboarding_stage`` recorded via the action endpoint (or seed).
    2. Archived when inactive.
    3. Progress-derived fallback for legacy rows with no explicit stage:
       agreement signed -> compliance_check; S8 aligned -> in_review; else submitted.
       Approval is NEVER inferred — completing the checklist alone does not
       approve a fork; a human must record it.
    """
    meta = fork.metadata_json or {}
    explicit_stage = meta.get("onboarding_stage")
    if explicit_stage:
        return explicit_stage
    if not fork.is_active:
        return "archived"
    if compliance.checks[1].passed:  # agreement signed
        return "compliance_check"
    if compliance.checks[0].passed:  # s8 aligned
        return "in_review"
    return "submitted"


@router.get("/{fork_id}/onboarding", response_model=ForkOnboardingDetailOut)
async def get_fork_onboarding_detail(
    fork_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> ForkOnboardingDetailOut:
    await require_permission(db, current_user, "forks.read")
    fork = await _load_fork_or_404(db, fork_id)

    members_result = await db.execute(
        select(ForkMember).where(ForkMember.fork_id == fork.id, ForkMember.is_active.is_(True))
    )
    members = list(members_result.scalars().all())
    compliance = evaluate_fork_compliance(fork, members)
    stage = _current_stage(fork, compliance)
    checklist = _get_checklist(fork)

    next_stage: str | None = None
    blockers: list[str] = []
    if stage in STAGE_ORDER and stage != "approved":
        idx = STAGE_ORDER.index(stage)
        next_stage = STAGE_ORDER[idx + 1]
        done = {s.key for s in checklist if s.completed}
        for key in STAGE_EXIT_REQUIREMENTS.get(stage, []):
            if key not in done:
                label = next(s["label"] for s in ONBOARDING_STEPS if s["key"] == key)
                blockers.append(label)
        if next_stage == "approved" and compliance.overall_status != "compliant":
            blockers.append("All statutory compliance checks must pass")

    remedies = [check.remedy for check in compliance.checks if check.remedy]

    return ForkOnboardingDetailOut(
        fork_id=fork.id,
        city_name=fork.city_name,
        slug=fork.slug,
        stage=stage,
        checklist=checklist,
        next_stage=next_stage,
        next_stage_blockers=blockers,
        health_score=compliance.health_score,
        overall_status=compliance.overall_status,
        remedies=remedies,
    )


@router.patch("/{fork_id}/onboarding/checklist/{step_key}", response_model=ForkOnboardingDetailOut)
async def update_onboarding_step(
    fork_id: Annotated[uuid.UUID, ...],
    step_key: str,
    payload: OnboardingStepUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> ForkOnboardingDetailOut:
    await require_permission(db, current_user, "forks.write")
    fork = await _load_fork_or_404(db, fork_id)

    valid_keys = {step["key"] for step in ONBOARDING_STEPS}
    if step_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown onboarding step '{step_key}'.",
        )

    meta = dict(fork.metadata_json or {})
    checklist_state = dict(meta.get("onboarding_checklist", {}))
    step_state = dict(checklist_state.get(step_key, {}))
    step_state["completed"] = payload.completed
    step_state["completed_at"] = (
        datetime.now(timezone.utc).isoformat() if payload.completed else None
    )
    step_state["completed_by"] = str(current_user.user_id) if payload.completed else None
    checklist_state[step_key] = step_state
    meta["onboarding_checklist"] = checklist_state
    fork.metadata_json = meta

    write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="fork.onboarding.step_updated",
        target_type="fork",
        target_id=str(fork.id),
        metadata={"step": step_key, "completed": payload.completed},
    )
    await db.commit()
    await db.refresh(fork)
    return await get_fork_onboarding_detail(fork_id, db, current_user)


@router.post("/{fork_id}/onboarding/action", response_model=ForkOnboardingDetailOut)
async def fork_onboarding_action(
    fork_id: Annotated[uuid.UUID, ...],
    payload: ForkStageActionPayload,
    db: DbSession,
    current_user: CurrentUserDep,
) -> ForkOnboardingDetailOut:
    """Advance, reject, archive, or reactivate a fork through the onboarding pipeline."""
    await require_permission(db, current_user, "forks.write")
    fork = await _load_fork_or_404(db, fork_id)

    members_result = await db.execute(
        select(ForkMember).where(ForkMember.fork_id == fork.id, ForkMember.is_active.is_(True))
    )
    members = list(members_result.scalars().all())
    compliance = evaluate_fork_compliance(fork, members)
    stage = _current_stage(fork, compliance)
    action = payload.action

    meta = dict(fork.metadata_json or {})

    if action == "advance":
        if stage not in STAGE_ORDER or stage == "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fork at stage '{stage}' cannot be advanced.",
            )
        next_stage = STAGE_ORDER[STAGE_ORDER.index(stage) + 1]

        detail = await get_fork_onboarding_detail(fork_id, db, current_user)
        if detail.next_stage_blockers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": f"Cannot advance to '{next_stage}': requirements unmet.",
                    "blockers": detail.next_stage_blockers,
                },
            )

        meta["onboarding_stage"] = next_stage
        if next_stage == "approved":
            fork.is_active = True
        write_audit_entry(
            db,
            actor_id=current_user.user_id,
            action="fork.onboarding.advanced",
            target_type="fork",
            target_id=str(fork.id),
            metadata={"from": stage, "to": next_stage},
        )

    elif action == "reject":
        if stage == "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved forks cannot be rejected. Archive instead.",
            )
        if not payload.reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A rejection reason is required.",
            )
        meta["onboarding_stage"] = "archived"
        meta["archive_reason"] = payload.reason
        fork.is_active = False
        write_audit_entry(
            db,
            actor_id=current_user.user_id,
            action="fork.onboarding.rejected",
            target_type="fork",
            target_id=str(fork.id),
            metadata={"from": stage, "reason": payload.reason},
        )

    elif action == "archive":
        if not payload.reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An archival reason is required.",
            )
        meta["onboarding_stage"] = "archived"
        meta["archive_reason"] = payload.reason
        fork.is_active = False
        write_audit_entry(
            db,
            actor_id=current_user.user_id,
            action="fork.onboarding.archived",
            target_type="fork",
            target_id=str(fork.id),
            metadata={"from": stage, "reason": payload.reason},
        )

    elif action == "reactivate":
        if fork.is_active and stage != "archived":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fork is already active.",
            )
        meta["onboarding_stage"] = "submitted"
        meta.pop("archive_reason", None)
        fork.is_active = True
        write_audit_entry(
            db,
            actor_id=current_user.user_id,
            action="fork.onboarding.reactivated",
            target_type="fork",
            target_id=str(fork.id),
            metadata={},
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be one of: advance, reject, archive, reactivate",
        )

    fork.metadata_json = meta
    await db.commit()
    await db.refresh(fork)
    return await get_fork_onboarding_detail(fork_id, db, current_user)


# ---------------------------------------------------------------------------
# Fork member writes
# ---------------------------------------------------------------------------


@router.post("/{fork_id}/members", response_model=ForkMemberOut, status_code=status.HTTP_201_CREATED)
async def add_fork_member(
    fork_id: Annotated[uuid.UUID, ...],
    payload: ForkMemberCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> ForkMember:
    await require_permission(db, current_user, "forks.members.write")
    fork = await _load_fork_or_404(db, fork_id)

    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    existing_result = await db.execute(
        select(ForkMember).where(
            ForkMember.fork_id == fork.id, ForkMember.user_id == payload.user_id
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing and existing.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already an active member of this fork.",
        )
    if existing:
        existing.is_active = True
        existing.local_role = payload.local_role
        existing.track = payload.track
        existing.left_at = None
        member = existing
    else:
        member = ForkMember(
            user_id=payload.user_id,
            fork_id=fork.id,
            track=payload.track,
            local_role=payload.local_role,
        )
        db.add(member)

    write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="fork.member.added",
        target_type="fork",
        target_id=str(fork.id),
        metadata={"member_user_id": str(payload.user_id), "local_role": payload.local_role},
    )
    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/{fork_id}/members/{member_id}", response_model=ForkMemberOut)
async def remove_fork_member(
    fork_id: Annotated[uuid.UUID, ...],
    member_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> ForkMember:
    await require_permission(db, current_user, "forks.members.write")
    await _load_fork_or_404(db, fork_id)

    member = await db.get(ForkMember, member_id)
    if not member or member.fork_id != fork_id or not member.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork member not found.")

    member.is_active = False
    member.left_at = datetime.now(timezone.utc)
    write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="fork.member.removed",
        target_type="fork",
        target_id=str(fork_id),
        metadata={"member_user_id": str(member.user_id)},
    )
    await db.commit()
    await db.refresh(member)
    return member
