"""
Finance router — GOBITSNBYTES FOUNDATION Virtual Ledger API.

Internal virtual budgeting system for tracking allocations, expenses, and transfers
across forks and departments. All balances are tracked in the database as virtual
ledger entries — no real banking integration is active. Requires IAM-based
authentication via signed internal proxy headers and finance.* permissions.

Governance controls implemented here (docs/legal_governance_rules.md §2–3):
    * Self-approval prohibition — approve/reject return 403 when the acting
      principal is the requester (IOM v2.0 §3.2).
    * Dual authorization band — commitments at or above
      settings.finance_dual_approval_threshold_paise require TWO DISTINCT
      approvers (neither the requester) before funds move (OKF Rule 35).
    * Append-only audit trail for every money-request lifecycle event and
      simulated card charge.

Dual-approval storage decision: money_requests has no metadata column and new
tables/columns are out of scope (migrations owned elsewhere). Redis was ruled
out because pending-approval state is compliance-critical and must survive
restarts (and tests run without Redis). Instead, each above-threshold approval
is persisted as an append-only AuditLog row (action
"finance.request.approval_recorded", target_type "money_request",
target_id = request UUID, actor = approver); completion is determined by
COUNT(DISTINCT actor_id) over those rows. This reuses an existing table,
commits atomically with the approve transaction, and doubles as the forensic
signature trail.

Future: Wire to RazorpayX for real virtual account creation and payouts via
the app.services.razorpayx_adapter seam.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, func, select

from app.db.models import AuditLog, MoneyRequest, VirtualAccount, VirtualCard, VirtualTransaction
from app.dependencies import AppSettings, CurrentUserDep, DbSession
from app.iam.audit import write_audit_entry
from app.iam.policy import can, require_permission
from app.schemas.finance import (
    MoneyRequestCreate,
    MoneyRequestOut,
    MoneyRequestReview,
    Section8ComplianceOut,
    VirtualAccountCreate,
    VirtualAccountOut,
    VirtualAccountUpdate,
    VirtualCardCreate,
    VirtualCardOut,
    VirtualCardUpdate,
    VirtualTransactionOut,
    CardSimulationPayload,
)
from app.services.razorpayx_adapter import (
    build_adapter,
    CardIssueRequest,
    LedgerAccountRequest,
)

router = APIRouter(prefix="/api/finance", tags=["finance"])

# Audit actions (append-only trail)
AUDIT_REQUEST_CREATED = "finance.request.created"
AUDIT_APPROVAL_RECORDED = "finance.request.approval_recorded"
AUDIT_REQUEST_APPROVED = "finance.request.approved"
AUDIT_REQUEST_REJECTED = "finance.request.rejected"
AUDIT_CARD_CHARGED = "finance.card.charged"

_AUDIT_TARGET_MONEY_REQUEST = "money_request"
_AUDIT_TARGET_CARD = "virtual_card"

# OKF Rule 35 dual-authorization constants
REQUIRED_APPROVERS = 2

_FY_PATTERN = re.compile(r"^\d{4}-\d{2}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_fy_label(today: date | None = None) -> str:
    """Label the financial year containing ``today`` (FY runs 1 Apr – 31 Mar).

    26 Aug 2026 -> "2026-27"; 12 Feb 2026 -> "2025-26".
    """
    today = today or datetime.now(timezone.utc).date()
    start_year = today.year if today.month >= 4 else today.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _dual_applies(req: MoneyRequest, settings: AppSettings) -> bool:
    """True when the request falls in the dual-authorization band."""
    return (
        settings.finance_dual_approval_enabled
        and req.amount_paise >= settings.finance_dual_approval_threshold_paise
    )


async def _count_distinct_approvers(db, request_id: uuid.UUID) -> int:
    """Count DISTINCT approvers recorded in the audit trail for a request."""
    res = await db.execute(
        select(func.count(distinct(AuditLog.actor_id))).where(
            AuditLog.action == AUDIT_APPROVAL_RECORDED,
            AuditLog.target_type == _AUDIT_TARGET_MONEY_REQUEST,
            AuditLog.target_id == str(request_id),
            AuditLog.actor_id.is_not(None),
        )
    )
    return int(res.scalar() or 0)


async def _approval_counts_by_id(db, request_ids: set[str]) -> dict[str, int]:
    """Batch COUNT(DISTINCT actor_id) grouped by request id."""
    if not request_ids:
        return {}
    res = await db.execute(
        select(AuditLog.target_id, func.count(distinct(AuditLog.actor_id)))
        .where(
            AuditLog.action == AUDIT_APPROVAL_RECORDED,
            AuditLog.target_type == _AUDIT_TARGET_MONEY_REQUEST,
            AuditLog.target_id.in_(request_ids),
            AuditLog.actor_id.is_not(None),
        )
        .group_by(AuditLog.target_id)
    )
    return {row[0]: int(row[1]) for row in res.all()}


async def _serialize_requests(
    db, requests: list[MoneyRequest], settings: AppSettings
) -> list[MoneyRequestOut]:
    """Convert ORM rows to Out models, populating dual-approval progress fields."""
    outs = [MoneyRequestOut.model_validate(r) for r in requests]
    dual_ids = {str(r.id) for r, o in zip(requests, outs) if _dual_applies(r, settings)}
    if dual_ids:
        counts = await _approval_counts_by_id(db, dual_ids)
        for r, o in zip(requests, outs):
            key = str(r.id)
            if key in dual_ids:
                o.dual_approval_required = True
                o.approvals_count = counts.get(key, 0)
                o.required_approvals = REQUIRED_APPROVERS
    return outs


async def _require_finance(db, user, perm: str) -> None:
    """Check if the user is a finance admin OR has a specific finance permission constraint."""
    is_admin = await can(db, user, "finance.admin")
    if is_admin:
        return
    await require_permission(db, user, perm)


# ---------------------------------------------------------------------------
# Health & Info
# ---------------------------------------------------------------------------

@router.get("/health")
async def finance_health() -> dict:
    """Return health status details of the virtual finance services."""
    return {"status": "ok", "service": "finance"}


@router.get("/info")
async def finance_info(settings: AppSettings) -> dict:
    """Provide descriptive metadata and current contact information for GOBITSNBYTES FOUNDATION finance tracking."""
    return {
        "name": "GOBITSNBYTES FOUNDATION Finance API",
        "version": settings.app_version,
        "description": (
            "Internal virtual finance ledger for the bits&bytes network. "
            "Handles virtual budgeting, expense tracking, reimbursements, and "
            "financial reporting across all city forks. All balances are "
            "internal tracking entries — no real banking integration is active."
        ),
        "status": "active",
        "organization": "GOBITSNBYTES FOUNDATION",
        "banking_provider": "Virtual Ledger (RazorpayX planned)",
        "contact": "finance@gobitsnbytes.org",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Virtual Accounts
# ---------------------------------------------------------------------------

@router.get("/accounts", response_model=list[VirtualAccountOut])
async def list_accounts(
    db: DbSession,
    current_user: CurrentUserDep,
    active_only: Annotated[bool, Query()] = True,
) -> list[VirtualAccount]:
    """List virtual ledger accounts. Active-only toggle is enabled by default."""
    await _require_finance(db, current_user, "finance.accounts.read")
    stmt = select(VirtualAccount)
    if active_only:
        stmt = stmt.where(VirtualAccount.is_active.is_(True))
    stmt = stmt.order_by(VirtualAccount.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/accounts", response_model=VirtualAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: VirtualAccountCreate,
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> VirtualAccount:
    """Create a new virtual ledger account with a provider-issued account number.

    Goes through the RazorpayX adapter seam; the default paper adapter mints
    a unique VIRT-* number locally. Response shape is unchanged.
    """
    await _require_finance(db, current_user, "finance.accounts.create")

    adapter = build_adapter(settings, db)
    result = await adapter.create_account(
        LedgerAccountRequest(
            name=payload.name,
            owner_id=payload.owner_id,
            description=payload.description,
        )
    )

    account = VirtualAccount(
        owner_id=payload.owner_id,
        name=payload.name,
        description=payload.description,
        account_number=result.account_number,
        ifsc=result.ifsc,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/accounts/{account_id}", response_model=VirtualAccountOut)
async def get_account(
    account_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
) -> VirtualAccount:
    """Retrieve details for a specific virtual ledger account by UUID."""
    await _require_finance(db, current_user, "finance.accounts.read")
    account = await db.get(VirtualAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return account


@router.patch("/accounts/{account_id}", response_model=VirtualAccountOut)
async def update_account(
    account_id: uuid.UUID,
    payload: VirtualAccountUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> VirtualAccount:
    """Update profile configuration or status values for a virtual ledger account."""
    await _require_finance(db, current_user, "finance.accounts.manage")
    account = await db.get(VirtualAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_account(
    account_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    """Soft delete/deactivate a virtual ledger account."""
    await _require_finance(db, current_user, "finance.accounts.manage")
    account = await db.get(VirtualAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    account.is_active = False
    await db.commit()


@router.get("/accounts/{account_id}/cards", response_model=list[VirtualCardOut])
async def list_account_cards(
    account_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[VirtualCard]:
    """List virtual debit/credit cards linked to a specific virtual ledger account."""
    await _require_finance(db, current_user, "finance.cards.read")
    result = await db.execute(
        select(VirtualCard).where(VirtualCard.account_id == account_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Virtual Cards
# ---------------------------------------------------------------------------

@router.get("/cards", response_model=list[VirtualCardOut])
async def list_cards(
    db: DbSession,
    current_user: CurrentUserDep,
    active_only: Annotated[bool, Query()] = True,
) -> list[VirtualCard]:
    """List all issued virtual cards. Active-only toggle is enabled by default."""
    await _require_finance(db, current_user, "finance.cards.read")
    stmt = select(VirtualCard)
    if active_only:
        stmt = stmt.where(VirtualCard.is_active.is_(True))
    stmt = stmt.order_by(VirtualCard.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/cards", response_model=VirtualCardOut, status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: VirtualCardCreate,
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> VirtualCard:
    """Issue a new virtual card linked to a parent account, establishing spending limits.

    Goes through the RazorpayX adapter seam; the default paper adapter mints
    the card suffix locally. Response shape is unchanged.
    """
    await _require_finance(db, current_user, "finance.cards.create")
    account = await db.get(VirtualAccount, payload.account_id)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found or inactive.")

    adapter = build_adapter(settings, db)
    issue_result = await adapter.issue_card(
        CardIssueRequest(
            account_id=payload.account_id,
            holder_id=payload.holder_id,
            card_name=payload.card_name,
            card_type=payload.card_type,
            expires_month=payload.expires_month,
            expires_year=payload.expires_year,
            daily_limit_paise=payload.daily_limit_paise,
            monthly_limit_paise=payload.monthly_limit_paise,
        )
    )

    card = VirtualCard(
        account_id=payload.account_id,
        holder_id=payload.holder_id,
        card_name=payload.card_name,
        last_four=issue_result.last_four,
        card_type=issue_result.card_type,
        expires_month=payload.expires_month,
        expires_year=payload.expires_year,
        daily_limit_paise=payload.daily_limit_paise,
        monthly_limit_paise=payload.monthly_limit_paise,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.get("/cards/{card_id}", response_model=VirtualCardOut)
async def get_card(
    card_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
) -> VirtualCard:
    """Get profile information for a specific virtual card by UUID."""
    await _require_finance(db, current_user, "finance.cards.read")
    card = await db.get(VirtualCard, card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    return card


@router.patch("/cards/{card_id}", response_model=VirtualCardOut)
async def update_card(
    card_id: uuid.UUID,
    payload: VirtualCardUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> VirtualCard:
    """Modify details, active status, or spending limit thresholds for a virtual card."""
    await _require_finance(db, current_user, "finance.cards.manage")
    card = await db.get(VirtualCard, card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_card(
    card_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    """Soft delete/deactivate a virtual card."""
    await _require_finance(db, current_user, "finance.cards.manage")
    card = await db.get(VirtualCard, card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    card.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Money Requests
# ---------------------------------------------------------------------------

@router.get("/requests", response_model=list[MoneyRequestOut])
async def list_requests(
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MoneyRequestOut]:
    """List money requests, with optional filters for pending/approved status."""
    await _require_finance(db, current_user, "finance.requests.read")
    stmt = select(MoneyRequest).order_by(MoneyRequest.created_at.desc()).limit(limit).offset(offset)
    if status_filter:
        stmt = stmt.where(MoneyRequest.status == status_filter)
    result = await db.execute(stmt)
    requests = list(result.scalars().all())
    return await _serialize_requests(db, requests, settings)


@router.post("/requests", response_model=MoneyRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: MoneyRequestCreate,
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> MoneyRequestOut:
    """Submit a money draw request to pull balance into a virtual account."""
    await _require_finance(db, current_user, "finance.requests.create")

    # Validate destination account
    to_account = await db.get(VirtualAccount, payload.to_account_id)
    if not to_account or not to_account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination account not found or inactive.")

    # If from_account specified, validate it
    if payload.from_account_id:
        from_account = await db.get(VirtualAccount, payload.from_account_id)
        if not from_account or not from_account.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source account not found or inactive.")
        if payload.from_account_id == payload.to_account_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination accounts must be different.")

    req = MoneyRequest(
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        requester_id=current_user.user_id,
        amount_paise=payload.amount_paise,
        description=payload.description,
    )
    db.add(req)
    await db.flush()
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action=AUDIT_REQUEST_CREATED,
        target_type=_AUDIT_TARGET_MONEY_REQUEST,
        target_id=str(req.id),
        metadata={
            "amount_paise": req.amount_paise,
            "description": req.description,
            "to_account_id": str(req.to_account_id),
            "from_account_id": str(req.from_account_id) if req.from_account_id else None,
        },
    )
    await db.commit()
    await db.refresh(req)
    return (await _serialize_requests(db, [req], settings))[0]


@router.get("/requests/{request_id}", response_model=MoneyRequestOut)
async def get_request(
    request_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> MoneyRequestOut:
    """Retrieve details for a specific money request by UUID."""
    await _require_finance(db, current_user, "finance.requests.read")
    req = await db.get(MoneyRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return (await _serialize_requests(db, [req], settings))[0]


@router.post("/requests/{request_id}/approve", response_model=MoneyRequestOut)
async def approve_request(
    request_id: uuid.UUID,
    payload: MoneyRequestReview,
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> MoneyRequestOut:
    """Approve a pending money request.

    Governance (IOM v2.0 §3.2 / OKF Rule 35):
      * Self-approval is prohibited — a requester can never approve (or
        reject) their own request; attempting so returns 403.
      * Requests at or above the dual-authorization threshold complete only
        after TWO DISTINCT approvers. Each qualifying approval is recorded as
        an append-only audit row; funds move on the approval that reaches the
        second distinct approver.
    """
    await _require_finance(db, current_user, "finance.requests.approve")
    req_result = await db.execute(
        select(MoneyRequest).where(MoneyRequest.id == request_id).with_for_update()
    )
    req = req_result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    # Self-approval prohibition — no exceptions, not even for finance admins
    if req.requester_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval is prohibited: the requester cannot review their own money request.",
        )

    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Request is already {req.status}.")

    to_account_result = await db.execute(
        select(VirtualAccount)
        .where(VirtualAccount.id == req.to_account_id)
        .with_for_update()
    )
    to_account = to_account_result.scalar_one_or_none()
    if not to_account or not to_account.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Destination account is missing or inactive.",
        )

    from_account = None
    if req.from_account_id:
        from_account_result = await db.execute(
            select(VirtualAccount)
            .where(VirtualAccount.id == req.from_account_id)
            .with_for_update()
        )
        from_account = from_account_result.scalar_one_or_none()
        if not from_account or not from_account.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Source account is missing or inactive.",
            )
        if from_account.balance_paise < req.amount_paise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source account has insufficient balance.",
            )

    dual_required = _dual_applies(req, settings)

    # Record this approval as an append-only audit signature, then count how
    # many DISTINCT approvers have signed so far (flush makes it visible).
    # Repeat approvals by the same person do not create extra signatures.
    if dual_required:
        already_signed = await db.execute(
            select(AuditLog.id).where(
                AuditLog.action == AUDIT_APPROVAL_RECORDED,
                AuditLog.target_type == _AUDIT_TARGET_MONEY_REQUEST,
                AuditLog.target_id == str(req.id),
                AuditLog.actor_id == current_user.user_id,
            )
        )
        if already_signed.scalar_one_or_none() is None:
            await write_audit_entry(
                db,
                actor_id=current_user.user_id,
                action=AUDIT_APPROVAL_RECORDED,
                target_type=_AUDIT_TARGET_MONEY_REQUEST,
                target_id=str(req.id),
                metadata={
                    "amount_paise": req.amount_paise,
                    "threshold_paise": settings.finance_dual_approval_threshold_paise,
                    "note": payload.note,
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await db.flush()

    approvals_count = (
        await _count_distinct_approvers(db, req.id) if dual_required else 1
    )

    if dual_required and approvals_count < REQUIRED_APPROVERS:
        # First signature of a joint commitment — hold funds movement until a
        # second distinct approver signs. Request stays pending.
        await db.commit()
        await db.refresh(req)
        out = MoneyRequestOut.model_validate(req)
        out.dual_approval_required = True
        out.approvals_count = approvals_count
        out.required_approvals = REQUIRED_APPROVERS
        return out

    # Final (or sole) approval — move balances (paper only)
    to_account.balance_paise += req.amount_paise
    if from_account:
        from_account.balance_paise -= req.amount_paise

    transaction = VirtualTransaction(
        source_account_id=req.from_account_id,
        destination_account_id=req.to_account_id,
        amount_paise=req.amount_paise,
        reference_type="money_request",
        reference_id=req.id,
        description=f"Approved money request: {req.description}",
    )
    db.add(transaction)

    req.status = "approved"
    req.reviewed_by = current_user.user_id
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_note = payload.note

    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action=AUDIT_REQUEST_APPROVED,
        target_type=_AUDIT_TARGET_MONEY_REQUEST,
        target_id=str(req.id),
        metadata={
            "amount_paise": req.amount_paise,
            "dual_approval_required": dual_required,
            "approvals_count": approvals_count,
            "note": payload.note,
        },
    )

    await db.commit()
    await db.refresh(req)
    return (await _serialize_requests(db, [req], settings))[0]


@router.post("/requests/{request_id}/reject", response_model=MoneyRequestOut)
async def reject_request(
    request_id: uuid.UUID,
    payload: MoneyRequestReview,
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> MoneyRequestOut:
    """Reject a pending money request.

    The self-approval prohibition applies here too: requesters cannot reject
    their own requests (IOM v2.0 §3.2).
    """
    await _require_finance(db, current_user, "finance.requests.approve")
    req = await db.get(MoneyRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    # Self-approval prohibition — mirrors the approve endpoint
    if req.requester_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-review is prohibited: the requester cannot reject their own money request.",
        )

    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Request is already {req.status}.")

    req.status = "rejected"
    req.reviewed_by = current_user.user_id
    req.reviewed_at = datetime.now(timezone.utc)
    req.review_note = payload.note

    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action=AUDIT_REQUEST_REJECTED,
        target_type=_AUDIT_TARGET_MONEY_REQUEST,
        target_id=str(req.id),
        metadata={
            "amount_paise": req.amount_paise,
            "note": payload.note,
        },
    )

    await db.commit()
    await db.refresh(req)
    return MoneyRequestOut.model_validate(req)


# ---------------------------------------------------------------------------
# Virtual Ledger Transactions & Simulation
# ---------------------------------------------------------------------------

@router.get("/transactions", response_model=list[VirtualTransactionOut])
async def list_all_transactions(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[VirtualTransaction]:
    """List recent transactions foundation-wide (for admins) or for owned accounts (for users)."""
    # Check if user has admin permission
    is_admin = await can(db, current_user, "finance.admin")
    
    if is_admin:
        stmt = select(VirtualTransaction).order_by(VirtualTransaction.created_at.desc()).limit(limit).offset(offset)
    else:
        # Users can only see transactions involving accounts they own
        user_accounts_stmt = select(VirtualAccount.id).where(VirtualAccount.owner_id == current_user.user_id)
        user_accounts_result = await db.execute(user_accounts_stmt)
        user_account_ids = user_accounts_result.scalars().all()
        
        if not user_account_ids:
            return []
            
        stmt = (
            select(VirtualTransaction)
            .where(
                VirtualTransaction.source_account_id.in_(user_account_ids) |
                VirtualTransaction.destination_account_id.in_(user_account_ids)
            )
            .order_by(VirtualTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/accounts/{account_id}/transactions", response_model=list[VirtualTransactionOut])
async def list_account_transactions(
    account_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[VirtualTransaction]:
    """List ledger transactions where target account is source or destination."""
    await _require_finance(db, current_user, "finance.accounts.read")
    account = await db.get(VirtualAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    
    stmt = (
        select(VirtualTransaction)
        .where(
            (VirtualTransaction.source_account_id == account_id) |
            (VirtualTransaction.destination_account_id == account_id)
        )
        .order_by(VirtualTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/cards/{card_id}/simulate-charge", response_model=VirtualTransactionOut)
async def simulate_card_charge(
    card_id: uuid.UUID,
    payload: CardSimulationPayload,
    db: DbSession,
    current_user: CurrentUserDep,
) -> VirtualTransaction:
    """Simulate a credit/debit card transaction, verifying balance and spending limits."""
    # 1. Fetch VirtualCard and verify
    card_result = await db.execute(
        select(VirtualCard).where(VirtualCard.id == card_id).with_for_update()
    )
    card = card_result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
        
    # Check if active
    if not card.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Card is inactive.")
        
    # Check permission: holder of the card or finance admin
    if card.holder_id != current_user.user_id:
        await _require_finance(db, current_user, "finance.cards.manage")
        
    # 2. Fetch parent account
    account_result = await db.execute(
        select(VirtualAccount)
        .where(VirtualAccount.id == card.account_id)
        .with_for_update()
    )
    account = account_result.scalar_one_or_none()
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent virtual account not found or inactive.")
        
    # 3. Check account balance
    if account.balance_paise < payload.amount_paise:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decline: Insufficient balance. Card requires {payload.amount_paise} paise, account balance is {account.balance_paise} paise."
        )
        
    # 4. Check card limits (daily and monthly)
    # Daily Limit Check (last 24 hours)
    if card.daily_limit_paise is not None:
        cutoff_24h = datetime.now(timezone.utc) - timedelta(days=1)
        daily_sum_stmt = (
            select(func.sum(VirtualTransaction.amount_paise))
            .where(
                VirtualTransaction.reference_type == "card_charge",
                VirtualTransaction.reference_id == card.id,
                VirtualTransaction.created_at >= cutoff_24h
            )
        )
        daily_sum_res = await db.execute(daily_sum_stmt)
        daily_spent = daily_sum_res.scalar() or 0
        if daily_spent + payload.amount_paise > card.daily_limit_paise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decline: Transaction exceeds daily limit. Spent: {daily_spent} paise, Limit: {card.daily_limit_paise} paise."
            )
            
    # Monthly Limit Check (current calendar month)
    if card.monthly_limit_paise is not None:
        now = datetime.now(timezone.utc)
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        monthly_sum_stmt = (
            select(func.sum(VirtualTransaction.amount_paise))
            .where(
                VirtualTransaction.reference_type == "card_charge",
                VirtualTransaction.reference_id == card.id,
                VirtualTransaction.created_at >= start_of_month
            )
        )
        monthly_sum_res = await db.execute(monthly_sum_stmt)
        monthly_spent = monthly_sum_res.scalar() or 0
        if monthly_spent + payload.amount_paise > card.monthly_limit_paise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decline: Transaction exceeds monthly limit. Spent: {monthly_spent} paise, Limit: {card.monthly_limit_paise} paise."
            )
            
    # 5. Atomic Update: decrement parent account balance
    account.balance_paise -= payload.amount_paise
    
    # Create the VirtualTransaction
    transaction = VirtualTransaction(
        source_account_id=card.account_id,
        destination_account_id=None,
        amount_paise=payload.amount_paise,
        reference_type="card_charge",
        reference_id=card.id,
        description=f"Card charge: {payload.merchant} - {payload.description}",
    )
    db.add(transaction)

    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action=AUDIT_CARD_CHARGED,
        target_type=_AUDIT_TARGET_CARD,
        target_id=str(card.id),
        metadata={
            "amount_paise": payload.amount_paise,
            "merchant": payload.merchant,
            "description": payload.description,
            "card_last_four": card.last_four,
            "account_id": str(card.account_id),
        },
    )
    
    await db.commit()
    await db.refresh(transaction)
    return transaction


# ---------------------------------------------------------------------------
# Section 8 Compliance Disclosure
# ---------------------------------------------------------------------------

@router.get("/compliance", response_model=Section8ComplianceOut)
async def get_section8_compliance(
    db: DbSession,
    current_user: CurrentUserDep,
    settings: AppSettings,
) -> Section8ComplianceOut:
    """Governance disclosure for GOBITSNBYTES FOUNDATION (Section 8, Companies Act 2013).

    Attests the hard prohibitions from docs/legal_governance_rules.md §3 with
    their governing citations, reports the live dual-authorization band
    (OKF Rule 35), and surfaces ledger state: pending commitments above the
    threshold awaiting joint approval.
    """
    await _require_finance(db, current_user, "finance.requests.read")

    threshold = settings.finance_dual_approval_threshold_paise
    open_above_res = await db.execute(
        select(func.count())
        .select_from(MoneyRequest)
        .where(MoneyRequest.status == "pending", MoneyRequest.amount_paise >= threshold)
    )
    open_above = int(open_above_res.scalar() or 0)

    rules = [
        {
            "rule": "cash_collection_prohibited",
            "status": "attested",
            "citation": "IOM v2.0 §3.1 — No Cash Collections outside approved Foundation programs.",
        },
        {
            "rule": "personal_upi_routing_prohibited",
            "status": "attested",
            "citation": "IOM v2.0 §3.1 — No Personal UPI Routing (Paytm/GPay/PhonePe) for fees, sponsorships, or donations.",
        },
        {
            "rule": "local_bank_accounts_prohibited",
            "status": "attested",
            "citation": "IOM v2.0 §3.1 — No Informal Bank Accounts in a Fork's name or under the bits&bytes™ brand.",
        },
        {
            "rule": "sponsorship_flows_upstream_first",
            "status": "attested",
            "citation": "IOM v2.0 §3.3 — Sponsorships executed upstream; funds route to Foundation accounts before allocation.",
        },
        {
            "rule": "self_approval_prohibited",
            "status": "enforced",
            "citation": "IOM v2.0 §3.2 — No person may approve a payment to themselves.",
        },
        {
            "rule": "dual_authorization",
            "status": "enforced" if settings.finance_dual_approval_enabled else "disabled",
            "citation": f"IOM v2.0 §3.2 / OKF Rule 35 — Dual approval required above ₹{threshold / 100:,.0f}.",
        },
    ]

    flags_ok = all(
        [
            True,  # cash_collection_prohibited — paper ledger has no cash rails
            True,  # personal_upi_routing_prohibited — no UPI rails exist
            True,  # local_bank_accounts_prohibited — single Foundation account underneath
            True,  # sponsorship_flows_upstream_first — structural design of the ledger
        ]
    )
    overall_status = "compliant" if flags_ok and open_above == 0 else "warning"

    return Section8ComplianceOut(
        foundation_name="GOBITSNBYTES FOUNDATION",
        licence_number="Section 8 Licence No. 186266 (Central Registration Centre, Manesar)",
        incorporation_date="2026-06-02",
        corporate_status=(
            "Not-for-profit company limited by guarantee without share capital "
            "under Section 8 of the Companies Act, 2013 (Uttar Pradesh, India)."
        ),
        rules=rules,
        cash_collection_prohibited=True,
        personal_upi_routing_prohibited=True,
        local_bank_accounts_prohibited=True,
        sponsorship_flows_upstream_first=True,
        dual_auth_threshold_paise=threshold,
        dual_auth_enabled=settings.finance_dual_approval_enabled,
        fy_start_month=4,
        current_fy=_current_fy_label(),
        open_requests_above_threshold=open_above,
        overall_status=overall_status,
    )


# ---------------------------------------------------------------------------
# Financial Year Export (streaming CSV)
# ---------------------------------------------------------------------------

@router.get("/reports/fy")
async def export_fy_report(
    fy: Annotated[str, Query(description="Financial year label, e.g. 2026-27 (1 April – 31 March)")],
    db: DbSession,
    current_user: CurrentUserDep,
) -> StreamingResponse:
    """Stream the full-year virtual ledger as CSV.

    Requires finance.admin. The FY runs 1 April – 31 March; ``fy`` must match
    ^\\d{4}-\\d{2}$ and the short year must continue the start year.
    Columns: date, txn_type, account, counterparty, narration, amount_paise,
    direction (relative to `account`: outflow/inflow).
    """
    await require_permission(db, current_user, "finance.admin")

    if not _FY_PATTERN.match(fy):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid financial year format. Use YYYY-YY, e.g. 2026-27.",
        )
    start_year = int(fy[:4])
    end_short = int(fy[5:])
    if end_short != (start_year % 100) + 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Financial year must span 1 April to 31 March of the following year.",
        )

    range_start = datetime(start_year, 4, 1, tzinfo=timezone.utc)
    range_end = datetime(start_year + 1, 4, 1, tzinfo=timezone.utc)  # exclusive

    async def csv_rows():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "txn_type", "account", "counterparty", "narration", "amount_paise", "direction"])
        yield buf.getvalue()

        accounts_result = await db.execute(select(VirtualAccount))
        account_names = {a.id: a.name for a in accounts_result.scalars().all()}

        stmt = (
            select(VirtualTransaction)
            .where(
                VirtualTransaction.created_at >= range_start,
                VirtualTransaction.created_at < range_end,
            )
            .order_by(VirtualTransaction.created_at.asc())
        )
        stream_result = await db.stream(stmt)
        async for txn in stream_result.scalars():
            src_name = (
                account_names.get(txn.source_account_id, "Unknown Account")
                if txn.source_account_id
                else None
            )
            dst_name = (
                account_names.get(txn.destination_account_id, "Unknown Account")
                if txn.destination_account_id
                else None
            )
            if src_name and dst_name:
                account, counterparty, direction = src_name, dst_name, "outflow"
            elif src_name:
                account, counterparty, direction = src_name, "Treasury Pool / External", "outflow"
            elif dst_name:
                account, counterparty, direction = dst_name, "Treasury Pool / External", "inflow"
            else:
                account, counterparty, direction = "Treasury Pool", "External", "outflow"

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(
                [
                    txn.created_at.date().isoformat(),
                    txn.reference_type,
                    account,
                    counterparty,
                    txn.description,
                    txn.amount_paise,
                    direction,
                ]
            )
            yield buf.getvalue()

    return StreamingResponse(
        csv_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="fy_{fy}_ledger.csv"'},
    )
