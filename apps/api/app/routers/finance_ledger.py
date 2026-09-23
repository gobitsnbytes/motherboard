"""
Finance Ledger router — GOBITSNBYTES FOUNDATION.

Everything the paper virtual-ledger router (app.routers.finance) doesn't
cover: the immutable double-entry journal, fiscal period close, vouchers
(maker-checker payment/receipt/journal), donor & donation receipts (80G/12A/
FCRA/cash-limit guarded), vendor bills & TDS, budgets, reports, bank
reconciliation, legal-registration settings, and the RazorpayX payout seam.

See docs/finance_ledger_design.md for the design and legal citations.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.dependencies import AppSettings, CurrentUserDep, DbSession
from app.finance import compliance, numbering, reports
from app.finance import ledger as fin_ledger
from app.finance import storage as fin_storage
from app.finance.models import (
    Bill,
    BankStatementLine,
    Budget,
    Donation,
    Donor,
    FinDocument,
    FinOrgSettings,
    FiscalPeriod,
    JournalEntry,
    LedgerAccount,
    ORG_SETTINGS_SINGLETON_ID,
    Vendor,
    Voucher,
)
from app.finance.payout_provider import RazorpayXNotConfigured, build_payout_provider
from app.finance.schemas import (
    BankStatementLineMatch,
    BillCreate,
    BillPay,
    BudgetCreate,
    DonationCreate,
    DonorCreate,
    JournalEntryCreate,
    JournalEntryReverse,
    LedgerAccountCreate,
    OrgSettingsUpdate,
    VendorCreate,
    VoucherCreate,
    VoucherReview,
)
from app.iam.audit import write_audit_entry
from app.iam.policy import require_permission
from app.routers.finance import _require_finance

router = APIRouter(prefix="/api/finance", tags=["finance-ledger"])


def _csv_stream(
    filename: str, fieldnames: list[str], rows: list[dict]
) -> StreamingResponse:
    async def gen():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        yield buf.getvalue()
        for row in rows:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writerow({k: row.get(k, "") for k in fieldnames})
            yield buf.getvalue()

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cash_bank_code(payment_mode: str) -> str:
    return "1002" if payment_mode == "cash" else "1001"


# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------


@router.get("/ledger/accounts")
async def list_ledger_accounts(
    db: DbSession, current_user: CurrentUserDep
) -> list[dict]:
    await _require_finance(db, current_user, "finance.ledger.read")
    await fin_ledger.ensure_system_accounts(db)
    await db.commit()
    result = await db.execute(select(LedgerAccount).order_by(LedgerAccount.code))
    return [
        {
            "id": str(a.id),
            "code": a.code,
            "name": a.name,
            "account_type": a.account_type,
            "normal_balance": a.normal_balance,
            "fund_type": a.fund_type,
            "is_active": a.is_active,
            "is_system": a.is_system,
            "parent_id": str(a.parent_id) if a.parent_id else None,
        }
        for a in result.scalars().all()
    ]


@router.post("/ledger/accounts", status_code=status.HTTP_201_CREATED)
async def create_ledger_account(
    payload: LedgerAccountCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.ledger.post")
    parent_id = None
    if payload.parent_code:
        parent_result = await db.execute(
            select(LedgerAccount).where(LedgerAccount.code == payload.parent_code)
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Parent account not found."
            )
        parent_id = parent.id
    account = LedgerAccount(
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
        normal_balance=payload.normal_balance,
        fund_type=payload.fund_type,
        parent_id=parent_id,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return {"id": str(account.id), "code": account.code, "name": account.name}


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


@router.get("/ledger/entries")
async def list_journal_entries(
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    await _require_finance(db, current_user, "finance.ledger.read")
    stmt = (
        select(JournalEntry)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.posted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if fy:
        stmt = stmt.where(JournalEntry.fy_label == fy)
    result = await db.execute(stmt)
    entries = list(result.scalars().all())
    out = []
    for e in entries:
        reversed_flag = await fin_ledger.is_entry_reversed(db, e.id)
        out.append(
            {
                "id": str(e.id),
                "fy_label": e.fy_label,
                "entry_date": e.entry_date.isoformat(),
                "memo": e.memo,
                "source_type": e.source_type,
                "source_id": str(e.source_id) if e.source_id else None,
                "reverses_entry_id": str(e.reverses_entry_id)
                if e.reverses_entry_id
                else None,
                "is_reversed": reversed_flag,
                "lines": [
                    {
                        "account_code": line.account.code,
                        "account_name": line.account.name,
                        "debit_paise": line.debit_paise,
                        "credit_paise": line.credit_paise,
                        "description": line.description,
                    }
                    for line in sorted(e.lines, key=lambda ln: ln.line_no)
                ],
            }
        )
    return out


@router.post("/ledger/entries", status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    payload: JournalEntryCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    """Manual journal entry (adjustments, accruals not covered by a voucher)."""
    await _require_finance(db, current_user, "finance.ledger.post")
    entry = await fin_ledger.post_journal_entry(
        db,
        entry_date=payload.entry_date,
        memo=payload.memo,
        lines=[
            fin_ledger.JournalLineInput(
                account_id=line.account_id,
                debit_paise=line.debit_paise,
                credit_paise=line.credit_paise,
                description=line.description,
                project_tag=line.project_tag,
                fund_type=line.fund_type,
            )
            for line in payload.lines
        ],
        source_type="manual",
        posted_by=current_user.user_id,
    )
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.ledger.entry_posted",
        target_type="journal_entry",
        target_id=str(entry.id),
        metadata={"memo": entry.memo},
    )
    await db.commit()
    return {"id": str(entry.id), "fy_label": entry.fy_label}


@router.post("/ledger/entries/{entry_id}/reverse", status_code=status.HTTP_201_CREATED)
async def reverse_journal_entry(
    entry_id: uuid.UUID,
    payload: JournalEntryReverse,
    db: DbSession,
    current_user: CurrentUserDep,
) -> dict:
    """Post the correcting reversal entry. Maker-checker: you cannot reverse
    your own posting (mirrors the self-approval prohibition elsewhere)."""
    await _require_finance(db, current_user, "finance.ledger.post")
    original_result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id)
    )
    original = original_result.scalar_one_or_none()
    if not original:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Journal entry not found."
        )
    if original.posted_by == current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Maker-checker: you cannot reverse a journal entry you posted yourself.",
        )
    reversal = await fin_ledger.reverse_journal_entry(
        db, entry_id=entry_id, posted_by=current_user.user_id, memo=payload.memo
    )
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.ledger.entry_reversed",
        target_type="journal_entry",
        target_id=str(entry_id),
        metadata={"reversal_entry_id": str(reversal.id)},
    )
    await db.commit()
    return {"id": str(reversal.id), "reverses_entry_id": str(entry_id)}


# ---------------------------------------------------------------------------
# Fiscal periods
# ---------------------------------------------------------------------------


@router.get("/periods")
async def list_periods(db: DbSession, current_user: CurrentUserDep) -> list[dict]:
    await _require_finance(db, current_user, "finance.ledger.read")
    result = await db.execute(
        select(FiscalPeriod).order_by(FiscalPeriod.fy_label.desc())
    )
    return [
        {
            "fy_label": p.fy_label,
            "start_date": p.start_date.isoformat(),
            "end_date": p.end_date.isoformat(),
            "is_closed": p.is_closed,
            "opening_balances_posted": p.opening_balances_posted,
        }
        for p in result.scalars().all()
    ]


@router.post("/periods/{fy}/close")
async def close_period(fy: str, db: DbSession, current_user: CurrentUserDep) -> dict:
    await require_permission(db, current_user, "finance.admin")
    period = await fin_ledger.get_or_create_period(db, fy)
    period.is_closed = True
    period.closed_by = current_user.user_id
    period.closed_at = datetime.now(timezone.utc)
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.period.closed",
        target_type="fiscal_period",
        target_id=fy,
        metadata={},
    )
    await db.commit()
    return {"fy_label": fy, "is_closed": True}


@router.post("/periods/{fy}/reopen")
async def reopen_period(fy: str, db: DbSession, current_user: CurrentUserDep) -> dict:
    await require_permission(db, current_user, "finance.admin")
    period = await fin_ledger.get_or_create_period(db, fy)
    period.is_closed = False
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.period.reopened",
        target_type="fiscal_period",
        target_id=fy,
        metadata={},
    )
    await db.commit()
    return {"fy_label": fy, "is_closed": False}


# ---------------------------------------------------------------------------
# Vouchers
# ---------------------------------------------------------------------------


@router.get("/vouchers")
async def list_vouchers(
    db: DbSession,
    current_user: CurrentUserDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    await _require_finance(db, current_user, "finance.vouchers.read")
    stmt = select(Voucher).order_by(Voucher.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(Voucher.status == status_filter)
    result = await db.execute(stmt)
    return [_voucher_out(v) for v in result.scalars().all()]


def _voucher_out(v: Voucher) -> dict:
    return {
        "id": str(v.id),
        "voucher_type": v.voucher_type,
        "voucher_number": v.voucher_number,
        "fy_label": v.fy_label,
        "voucher_date": v.voucher_date.isoformat(),
        "narration": v.narration,
        "amount_paise": v.amount_paise,
        "payment_mode": v.payment_mode,
        "status": v.status,
        "created_by": str(v.created_by),
        "approved_by": str(v.approved_by) if v.approved_by else None,
        "bill_id": str(v.bill_id) if v.bill_id else None,
        "journal_entry_id": str(v.journal_entry_id) if v.journal_entry_id else None,
        "created_at": v.created_at.isoformat(),
    }


@router.post("/vouchers", status_code=status.HTTP_201_CREATED)
async def create_voucher(
    payload: VoucherCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.vouchers.create")

    if payload.voucher_type == "payment":
        compliance.check_cash_payment(payload.amount_paise, payload.payment_mode)
        if payload.debit_account_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Payment vouchers need a debit_account_id (the expense/payable being paid).",
            )
    elif payload.voucher_type == "receipt":
        compliance.check_cash_receipt(payload.amount_paise, payload.payment_mode)
        if payload.credit_account_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Receipt vouchers need a credit_account_id (the income/receivable received).",
            )
    else:
        if payload.debit_account_id is None or payload.credit_account_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Journal vouchers need both debit_account_id and credit_account_id.",
            )

    fy_label = fin_ledger.fy_label_for(payload.voucher_date)
    await fin_ledger.assert_period_open(db, fy_label)

    voucher = Voucher(
        voucher_type=payload.voucher_type,
        fy_label=fy_label,
        voucher_date=payload.voucher_date,
        narration=payload.narration,
        amount_paise=payload.amount_paise,
        debit_account_id=payload.debit_account_id,
        credit_account_id=payload.credit_account_id,
        payment_mode=payload.payment_mode,
        party_type=payload.party_type,
        party_id=payload.party_id,
        bill_id=payload.bill_id,
        created_by=current_user.user_id,
        status="draft",
    )
    db.add(voucher)
    await db.commit()
    await db.refresh(voucher)
    return _voucher_out(voucher)


@router.post("/vouchers/{voucher_id}/submit")
async def submit_voucher(
    voucher_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.vouchers.create")
    voucher = await db.get(Voucher, voucher_id)
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Voucher not found.")
    if voucher.created_by != current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only the creator may submit this voucher.",
        )
    if voucher.status != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Voucher is already {voucher.status}."
        )
    voucher.status = "pending_approval"
    await db.commit()
    await db.refresh(voucher)
    return _voucher_out(voucher)


@router.post("/vouchers/{voucher_id}/approve")
async def approve_voucher(
    voucher_id: uuid.UUID,
    payload: VoucherReview,
    db: DbSession,
    current_user: CurrentUserDep,
) -> dict:
    """Maker-checker: approving allocates the sequential voucher number and
    posts the journal entry. The creator can never approve their own voucher."""
    await _require_finance(db, current_user, "finance.vouchers.approve")
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id).with_for_update()
    )
    voucher = result.scalar_one_or_none()
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Voucher not found.")
    if voucher.created_by == current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Self-approval is prohibited: the creator cannot approve their own voucher.",
        )
    if voucher.status != "pending_approval":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Voucher is {voucher.status}, not pending approval.",
        )

    await fin_ledger.assert_period_open(db, voucher.fy_label)
    bank_code = _cash_bank_code(voucher.payment_mode)
    if voucher.voucher_type == "payment":
        debit_id, credit_id = voucher.debit_account_id, voucher.credit_account_id
        if credit_id is None:
            credit_id = (await fin_ledger.get_or_create_account(db, bank_code)).id
    elif voucher.voucher_type == "receipt":
        debit_id, credit_id = voucher.debit_account_id, voucher.credit_account_id
        if debit_id is None:
            debit_id = (await fin_ledger.get_or_create_account(db, bank_code)).id
    else:
        debit_id, credit_id = voucher.debit_account_id, voucher.credit_account_id

    entry = await fin_ledger.post_journal_entry(
        db,
        entry_date=voucher.voucher_date,
        memo=voucher.narration,
        lines=[
            fin_ledger.JournalLineInput(
                account_id=debit_id,
                debit_paise=voucher.amount_paise,
                description=voucher.narration,
            ),
            fin_ledger.JournalLineInput(
                account_id=credit_id,
                credit_paise=voucher.amount_paise,
                description=voucher.narration,
            ),
        ],
        source_type="voucher",
        source_id=voucher.id,
        posted_by=current_user.user_id,
    )

    voucher.voucher_number = await numbering.next_document_number(
        db, voucher.fy_label, voucher.voucher_type
    )
    voucher.status = "posted"
    voucher.approved_by = current_user.user_id
    voucher.approved_at = datetime.now(timezone.utc)
    voucher.journal_entry_id = entry.id

    if voucher.bill_id:
        bill = await db.get(Bill, voucher.bill_id)
        if bill:
            bill.status = "paid"

    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.voucher.approved",
        target_type="voucher",
        target_id=str(voucher.id),
        metadata={"voucher_number": voucher.voucher_number, "note": payload.note},
    )
    await db.commit()
    await db.refresh(voucher)
    return _voucher_out(voucher)


@router.post("/vouchers/{voucher_id}/reject")
async def reject_voucher(
    voucher_id: uuid.UUID,
    payload: VoucherReview,
    db: DbSession,
    current_user: CurrentUserDep,
) -> dict:
    await _require_finance(db, current_user, "finance.vouchers.approve")
    voucher = await db.get(Voucher, voucher_id)
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Voucher not found.")
    if voucher.created_by == current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Self-review is prohibited: the creator cannot reject their own voucher.",
        )
    if voucher.status != "pending_approval":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Voucher is {voucher.status}, not pending approval.",
        )
    voucher.status = "rejected"
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.voucher.rejected",
        target_type="voucher",
        target_id=str(voucher.id),
        metadata={"note": payload.note},
    )
    await db.commit()
    await db.refresh(voucher)
    return _voucher_out(voucher)


@router.post("/vouchers/{voucher_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_voucher_document(
    voucher_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
) -> dict:
    await _require_finance(db, current_user, "finance.vouchers.create")
    voucher = await db.get(Voucher, voucher_id)
    if not voucher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Voucher not found.")
    content = await file.read()
    if len(content) > fin_storage.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 20MB upload limit.",
        )
    content_type = file.content_type or "application/octet-stream"
    if content_type not in fin_storage.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type: {content_type}"
        )
    storage_path, sha256 = fin_storage.save_upload(
        content, original_filename=file.filename or "upload"
    )
    doc = FinDocument(
        voucher_id=voucher.id,
        filename=file.filename or "upload",
        storage_path=storage_path,
        content_type=content_type,
        size_bytes=len(content),
        sha256=sha256,
        uploaded_by=current_user.user_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "size_bytes": doc.size_bytes,
        "sha256": doc.sha256,
    }


# ---------------------------------------------------------------------------
# Donors & donations
# ---------------------------------------------------------------------------


@router.get("/donors")
async def list_donors(db: DbSession, current_user: CurrentUserDep) -> list[dict]:
    await _require_finance(db, current_user, "finance.donations.read")
    result = await db.execute(select(Donor).order_by(Donor.name))
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "donor_type": d.donor_type,
            "pan": d.pan,
            "is_foreign_source": d.is_foreign_source,
        }
        for d in result.scalars().all()
    ]


@router.post("/donors", status_code=status.HTTP_201_CREATED)
async def create_donor(
    payload: DonorCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.donations.create")
    donor = Donor(**payload.model_dump())
    db.add(donor)
    await db.commit()
    await db.refresh(donor)
    return {"id": str(donor.id), "name": donor.name}


@router.get("/donations")
async def list_donations(
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
) -> list[dict]:
    await _require_finance(db, current_user, "finance.donations.read")
    stmt = select(Donation).order_by(Donation.created_at.desc())
    if fy:
        stmt = stmt.where(Donation.fy_label == fy)
    result = await db.execute(stmt)
    return [_donation_out(d) for d in result.scalars().all()]


def _donation_out(d: Donation) -> dict:
    return {
        "id": str(d.id),
        "donor_id": str(d.donor_id),
        "receipt_number": d.receipt_number,
        "fy_label": d.fy_label,
        "donation_date": d.donation_date.isoformat(),
        "amount_paise": d.amount_paise,
        "mode": d.mode,
        "purpose": d.purpose,
        "status": d.status,
        "claim_80g": d.claim_80g,
        "created_by": str(d.created_by),
        "confirmed_by": str(d.confirmed_by) if d.confirmed_by else None,
    }


@router.post("/donations", status_code=status.HTTP_201_CREATED)
async def create_donation(
    payload: DonationCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    """Record a donation (maker step). Ledger posting and the receipt number
    only happen on /confirm, by a different user."""
    await _require_finance(db, current_user, "finance.donations.create")
    donor = await db.get(Donor, payload.donor_id)
    if not donor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Donor not found.")

    compliance.check_cash_receipt(payload.amount_paise, payload.mode)
    org_settings = await _get_org_settings(db)
    compliance.check_fcra(
        is_foreign_source=donor.is_foreign_source,
        fcra_registration_no=org_settings.fcra_registration_no,
    )
    if payload.claim_80g and not donor.pan:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Donor PAN is required to issue an 80G-eligible receipt.",
        )

    donation = Donation(
        donor_id=payload.donor_id,
        fy_label=fin_ledger.fy_label_for(payload.donation_date),
        donation_date=payload.donation_date,
        amount_paise=payload.amount_paise,
        mode=payload.mode,
        purpose=payload.purpose,
        is_restricted_fund=payload.is_restricted_fund,
        claim_80g=payload.claim_80g,
        created_by=current_user.user_id,
        status="recorded",
    )
    db.add(donation)
    await db.commit()
    await db.refresh(donation)
    return _donation_out(donation)


@router.post("/donations/{donation_id}/confirm")
async def confirm_donation(
    donation_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.donations.approve")
    result = await db.execute(
        select(Donation).where(Donation.id == donation_id).with_for_update()
    )
    donation = result.scalar_one_or_none()
    if not donation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Donation not found.")
    if donation.created_by == current_user.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Self-approval is prohibited: the recorder cannot confirm their own donation.",
        )
    if donation.status != "recorded":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Donation is already {donation.status}."
        )

    await fin_ledger.assert_period_open(db, donation.fy_label)
    bank = await fin_ledger.get_or_create_account(db, _cash_bank_code(donation.mode))
    income_code = "4100" if donation.is_restricted_fund else "4000"
    income = await fin_ledger.get_or_create_account(db, income_code)
    entry = await fin_ledger.post_journal_entry(
        db,
        entry_date=donation.donation_date,
        memo=f"Donation received: {donation.purpose or 'general'}",
        lines=[
            fin_ledger.JournalLineInput(
                account_id=bank.id,
                debit_paise=donation.amount_paise,
                fund_type=income.fund_type,
            ),
            fin_ledger.JournalLineInput(
                account_id=income.id,
                credit_paise=donation.amount_paise,
                fund_type=income.fund_type,
            ),
        ],
        source_type="donation",
        source_id=donation.id,
        posted_by=current_user.user_id,
    )
    donation.receipt_number = await numbering.next_document_number(
        db, donation.fy_label, "donation"
    )
    donation.status = "confirmed"
    donation.confirmed_by = current_user.user_id
    donation.journal_entry_id = entry.id

    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.donation.confirmed",
        target_type="donation",
        target_id=str(donation.id),
        metadata={"receipt_number": donation.receipt_number},
    )
    await db.commit()
    await db.refresh(donation)
    return _donation_out(donation)


@router.get("/reports/form10bd")
async def export_form10bd(
    fy: Annotated[str, Query()], db: DbSession, current_user: CurrentUserDep
) -> StreamingResponse:
    """Form 10BD (statement of donations, Income-tax Rules r.18AB) CSV export."""
    await require_permission(db, current_user, "finance.reports.read")
    rows = await reports.form10bd_rows(db, fy)
    fields = [
        "donor_name",
        "unique_identification_number",
        "address",
        "type_of_donation",
        "mode_of_receipt",
        "date",
        "amount_paise",
        "receipt_number",
    ]
    return _csv_stream(f"form10bd_{fy}.csv", fields, rows)


# ---------------------------------------------------------------------------
# Vendors, bills & TDS
# ---------------------------------------------------------------------------


@router.get("/vendors")
async def list_vendors(db: DbSession, current_user: CurrentUserDep) -> list[dict]:
    await _require_finance(db, current_user, "finance.vendors.read")
    result = await db.execute(
        select(Vendor).where(Vendor.is_active.is_(True)).order_by(Vendor.name)
    )
    return [
        {
            "id": str(v.id),
            "name": v.name,
            "pan": v.pan,
            "gstin": v.gstin,
            "category": v.category,
        }
        for v in result.scalars().all()
    ]


@router.post("/vendors", status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.vendors.manage")
    vendor = Vendor(**payload.model_dump())
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    return {"id": str(vendor.id), "name": vendor.name}


def _bill_out(b: Bill) -> dict:
    return {
        "id": str(b.id),
        "vendor_id": str(b.vendor_id),
        "bill_number": b.bill_number,
        "bill_date": b.bill_date.isoformat(),
        "fy_label": b.fy_label,
        "amount_paise": b.amount_paise,
        "tds_section": b.tds_section,
        "tds_rate_bps": b.tds_rate_bps,
        "tds_amount_paise": b.tds_amount_paise,
        "status": b.status,
    }


@router.get("/bills")
async def list_bills(
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
) -> list[dict]:
    await _require_finance(db, current_user, "finance.vendors.read")
    stmt = select(Bill).order_by(Bill.created_at.desc())
    if fy:
        stmt = stmt.where(Bill.fy_label == fy)
    result = await db.execute(stmt)
    return [_bill_out(b) for b in result.scalars().all()]


@router.post("/bills", status_code=status.HTTP_201_CREATED)
async def create_bill(
    payload: BillCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    """Books the accrual: Debit Expense, Credit Payable (net of TDS) + TDS Payable."""
    await _require_finance(db, current_user, "finance.vendors.manage")
    vendor = await db.get(Vendor, payload.vendor_id)
    if not vendor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Vendor not found.")

    tds_amount = 0
    if payload.tds_section and payload.tds_rate_bps:
        tds_amount = (payload.amount_paise * payload.tds_rate_bps) // 10_000

    fy_label = fin_ledger.fy_label_for(payload.bill_date)
    await fin_ledger.assert_period_open(db, fy_label)
    expense_account = (
        await db.get(LedgerAccount, payload.expense_account_id)
        if payload.expense_account_id
        else await fin_ledger.get_or_create_account(db, "5000")
    )
    if not expense_account:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Expense account not found."
        )
    payable = await fin_ledger.get_or_create_account(db, "2001")

    lines = [
        fin_ledger.JournalLineInput(
            account_id=expense_account.id,
            debit_paise=payload.amount_paise,
            description=payload.bill_number,
        )
    ]
    net_payable = payload.amount_paise - tds_amount
    if net_payable > 0:
        lines.append(
            fin_ledger.JournalLineInput(
                account_id=payable.id,
                credit_paise=net_payable,
                description=payload.bill_number,
            )
        )
    if tds_amount > 0:
        tds_payable = await fin_ledger.get_or_create_account(db, "2100")
        lines.append(
            fin_ledger.JournalLineInput(
                account_id=tds_payable.id,
                credit_paise=tds_amount,
                description=f"TDS {payload.tds_section}",
            )
        )

    entry = await fin_ledger.post_journal_entry(
        db,
        entry_date=payload.bill_date,
        memo=f"Bill {payload.bill_number} — {vendor.name}",
        lines=lines,
        source_type="bill",
        posted_by=current_user.user_id,
    )
    bill = Bill(
        vendor_id=payload.vendor_id,
        bill_number=payload.bill_number,
        bill_date=payload.bill_date,
        fy_label=fy_label,
        amount_paise=payload.amount_paise,
        expense_account_id=expense_account.id,
        tds_section=payload.tds_section,
        tds_rate_bps=payload.tds_rate_bps,
        tds_amount_paise=tds_amount,
        gst_input_paise=payload.gst_input_paise,
        journal_entry_id=entry.id,
        created_by=current_user.user_id,
    )
    db.add(bill)
    await db.commit()
    await db.refresh(bill)
    return _bill_out(bill)


@router.post("/bills/{bill_id}/pay", status_code=status.HTTP_201_CREATED)
async def pay_bill(
    bill_id: uuid.UUID, payload: BillPay, db: DbSession, current_user: CurrentUserDep
) -> dict:
    """Creates a draft payment voucher clearing the payable. Goes through the
    normal voucher maker-checker flow — this endpoint does not move money."""
    await _require_finance(db, current_user, "finance.vendors.manage")
    bill = await db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Bill not found.")
    if bill.status == "paid":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Bill is already paid.")
    net_amount = bill.amount_paise - bill.tds_amount_paise
    compliance.check_cash_payment(net_amount, payload.payment_mode)
    payable = await fin_ledger.get_or_create_account(db, "2001")
    voucher_date = payload.voucher_date or datetime.now(timezone.utc).date()
    fy_label = fin_ledger.fy_label_for(voucher_date)
    await fin_ledger.assert_period_open(db, fy_label)
    voucher = Voucher(
        voucher_type="payment",
        fy_label=fy_label,
        voucher_date=voucher_date,
        narration=f"Payment for bill {bill.bill_number}",
        amount_paise=net_amount,
        debit_account_id=payable.id,
        payment_mode=payload.payment_mode,
        party_type="vendor",
        party_id=bill.vendor_id,
        bill_id=bill.id,
        created_by=current_user.user_id,
        status="draft",
    )
    db.add(voucher)
    await db.commit()
    await db.refresh(voucher)
    return _voucher_out(voucher)


@router.get("/reports/tds-quarterly")
async def export_tds_quarterly(
    fy: Annotated[str, Query()],
    quarter: Annotated[int, Query(ge=1, le=4)],
    db: DbSession,
    current_user: CurrentUserDep,
) -> StreamingResponse:
    """26Q-style quarterly TDS summary CSV, grouped by vendor/section."""
    await require_permission(db, current_user, "finance.reports.read")
    rows = await reports.tds_quarterly(db, fy, quarter)
    fields = [
        "vendor_name",
        "pan",
        "section",
        "rate_percent",
        "bill_amount_paise",
        "tds_amount_paise",
        "bill_date",
    ]
    return _csv_stream(f"tds_{fy}_q{quarter}.csv", fields, rows)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


@router.get("/budgets")
async def list_budgets(
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
) -> list[dict]:
    await _require_finance(db, current_user, "finance.budgets.read")
    stmt = select(Budget).order_by(Budget.fy_label.desc())
    if fy:
        stmt = stmt.where(Budget.fy_label == fy)
    result = await db.execute(stmt)
    return [
        {
            "id": str(b.id),
            "fy_label": b.fy_label,
            "account_id": str(b.account_id),
            "project_tag": b.project_tag,
            "budgeted_paise": b.budgeted_paise,
        }
        for b in result.scalars().all()
    ]


@router.post("/budgets", status_code=status.HTTP_201_CREATED)
async def create_budget(
    payload: BudgetCreate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.budgets.manage")
    budget = Budget(**payload.model_dump(), created_by=current_user.user_id)
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return {"id": str(budget.id)}


@router.get("/budgets/vs-actuals")
async def budgets_vs_actuals(
    db: DbSession, current_user: CurrentUserDep, fy: Annotated[str, Query()]
) -> list[dict]:
    await _require_finance(db, current_user, "finance.budgets.read")
    budgets_result = await db.execute(select(Budget).where(Budget.fy_label == fy))
    budgets = list(budgets_result.scalars().all())
    trial = {row["account_id"]: row for row in await reports.trial_balance(db, fy)}
    out = []
    for b in budgets:
        actual = trial.get(str(b.account_id), {}).get("balance_paise", 0)
        out.append(
            {
                "account_id": str(b.account_id),
                "project_tag": b.project_tag,
                "budgeted_paise": b.budgeted_paise,
                "actual_paise": actual,
                "variance_paise": b.budgeted_paise - actual,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/trial-balance", response_model=None)
async def report_trial_balance(
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
    csv_export: Annotated[bool, Query(alias="csv")] = False,
) -> list[dict] | StreamingResponse:
    await require_permission(db, current_user, "finance.reports.read")
    rows = await reports.trial_balance(db, fy)
    if csv_export:
        return _csv_stream(
            f"trial_balance_{fy or 'all'}.csv",
            [
                "code",
                "name",
                "account_type",
                "debit_total_paise",
                "credit_total_paise",
                "balance_paise",
            ],
            rows,
        )
    return rows


@router.get("/reports/income-expenditure")
async def report_income_expenditure(
    fy: Annotated[str, Query()], db: DbSession, current_user: CurrentUserDep
) -> dict:
    await require_permission(db, current_user, "finance.reports.read")
    return await reports.income_expenditure(db, fy)


@router.get("/reports/balance-sheet")
async def report_balance_sheet(
    db: DbSession,
    current_user: CurrentUserDep,
    as_of_fy: Annotated[str | None, Query()] = None,
) -> dict:
    await require_permission(db, current_user, "finance.reports.read")
    return await reports.balance_sheet(db, as_of_fy)


@router.get("/reports/receipts-payments", response_model=None)
async def report_receipts_payments(
    fy: Annotated[str, Query()],
    db: DbSession,
    current_user: CurrentUserDep,
    csv_export: Annotated[bool, Query(alias="csv")] = False,
) -> list[dict] | StreamingResponse:
    await require_permission(db, current_user, "finance.reports.read")
    rows = await reports.receipts_and_payments(db, fy)
    if csv_export:
        return _csv_stream(
            f"receipts_payments_{fy}.csv",
            ["date", "cash_account", "receipt_paise", "payment_paise", "narration"],
            rows,
        )
    return rows


@router.get("/reports/general-ledger/{account_id}", response_model=None)
async def report_general_ledger(
    account_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
    csv_export: Annotated[bool, Query(alias="csv")] = False,
) -> list[dict] | StreamingResponse:
    await require_permission(db, current_user, "finance.reports.read")
    rows = await reports.general_ledger(db, account_id, fy)
    if csv_export:
        return _csv_stream(
            f"general_ledger_{account_id}.csv",
            [
                "date",
                "narration",
                "debit_paise",
                "credit_paise",
                "running_balance_paise",
            ],
            rows,
        )
    return rows


@router.get("/reports/donors", response_model=None)
async def report_donors(
    db: DbSession,
    current_user: CurrentUserDep,
    fy: Annotated[str | None, Query()] = None,
    csv_export: Annotated[bool, Query(alias="csv")] = False,
) -> list[dict] | StreamingResponse:
    await require_permission(db, current_user, "finance.reports.read")
    rows = await reports.donor_report(db, fy)
    if csv_export:
        return _csv_stream(
            f"donor_report_{fy or 'all'}.csv",
            ["donor_name", "pan", "donor_type", "donation_count", "total_paise"],
            rows,
        )
    return rows


# ---------------------------------------------------------------------------
# Bank reconciliation
# ---------------------------------------------------------------------------


@router.post("/bank-rec/import", status_code=status.HTTP_201_CREATED)
async def import_bank_statement(
    db: DbSession, current_user: CurrentUserDep, file: UploadFile = File(...)
) -> dict:
    """CSV columns: date,description,amount_paise,direction (debit|credit)."""
    await _require_finance(db, current_user, "finance.bank_rec.manage")
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    batch_label = f"import-{datetime.now(timezone.utc).isoformat()}"
    count = 0
    for row in reader:
        try:
            db.add(
                BankStatementLine(
                    batch_label=batch_label,
                    statement_date=date.fromisoformat(row["date"].strip()),
                    description=row.get("description", ""),
                    amount_paise=int(row["amount_paise"]),
                    direction=row["direction"].strip().lower(),
                    imported_by=current_user.user_id,
                )
            )
            count += 1
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"Bad CSV row {row!r}: {exc}"
            ) from exc
    await db.commit()
    return {"batch_label": batch_label, "imported": count}


@router.get("/bank-rec/lines")
async def list_bank_lines(
    db: DbSession,
    current_user: CurrentUserDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[dict]:
    await _require_finance(db, current_user, "finance.bank_rec.manage")
    stmt = select(BankStatementLine).order_by(BankStatementLine.statement_date.desc())
    if status_filter:
        stmt = stmt.where(BankStatementLine.status == status_filter)
    result = await db.execute(stmt)
    return [
        {
            "id": str(line.id),
            "batch_label": line.batch_label,
            "statement_date": line.statement_date.isoformat(),
            "description": line.description,
            "amount_paise": line.amount_paise,
            "direction": line.direction,
            "status": line.status,
        }
        for line in result.scalars().all()
    ]


@router.post("/bank-rec/lines/{line_id}/match")
async def match_bank_line(
    line_id: uuid.UUID,
    payload: BankStatementLineMatch,
    db: DbSession,
    current_user: CurrentUserDep,
) -> dict:
    await _require_finance(db, current_user, "finance.bank_rec.manage")
    line = await db.get(BankStatementLine, line_id)
    if not line:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Statement line not found."
        )
    line.matched_journal_line_id = payload.journal_line_id
    line.status = "matched"
    await db.commit()
    return {"id": str(line.id), "status": line.status}


@router.post("/bank-rec/lines/{line_id}/ignore")
async def ignore_bank_line(
    line_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await _require_finance(db, current_user, "finance.bank_rec.manage")
    line = await db.get(BankStatementLine, line_id)
    if not line:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Statement line not found."
        )
    line.status = "ignored"
    await db.commit()
    return {"id": str(line.id), "status": line.status}


# ---------------------------------------------------------------------------
# Legal / registration settings
# ---------------------------------------------------------------------------


async def _get_org_settings(db: DbSession) -> FinOrgSettings:
    settings_row = await db.get(FinOrgSettings, ORG_SETTINGS_SINGLETON_ID)
    if settings_row is None:
        settings_row = FinOrgSettings(id=ORG_SETTINGS_SINGLETON_ID)
        db.add(settings_row)
        await db.flush()
    return settings_row


@router.get("/settings/org")
async def get_org_settings(db: DbSession, current_user: CurrentUserDep) -> dict:
    await _require_finance(db, current_user, "finance.settings.manage")
    s = await _get_org_settings(db)
    await db.commit()
    return {
        "pan": s.pan,
        "tan": s.tan,
        "gstin": s.gstin,
        "income_tax_80g_reg_no": s.income_tax_80g_reg_no,
        "income_tax_80g_valid_upto": s.income_tax_80g_valid_upto.isoformat()
        if s.income_tax_80g_valid_upto
        else None,
        "income_tax_12a_reg_no": s.income_tax_12a_reg_no,
        "fcra_registration_no": s.fcra_registration_no,
        "fcra_valid_upto": s.fcra_valid_upto.isoformat() if s.fcra_valid_upto else None,
    }


@router.patch("/settings/org")
async def update_org_settings(
    payload: OrgSettingsUpdate, db: DbSession, current_user: CurrentUserDep
) -> dict:
    await require_permission(db, current_user, "finance.settings.manage")
    s = await _get_org_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    s.updated_by = current_user.user_id
    await write_audit_entry(
        db,
        actor_id=current_user.user_id,
        action="finance.settings.org_updated",
        target_type="fin_org_settings",
        target_id=str(s.id),
        metadata=payload.model_dump(exclude_unset=True, mode="json"),
    )
    await db.commit()
    return await get_org_settings(db, current_user)


# ---------------------------------------------------------------------------
# RazorpayX payout seam (placeholder)
# ---------------------------------------------------------------------------


@router.get("/razorpayx/status")
async def razorpayx_status(
    db: DbSession, current_user: CurrentUserDep, settings: AppSettings
) -> dict:
    await _require_finance(db, current_user, "finance.accounts.read")
    provider = build_payout_provider(settings)
    return {
        "configured": provider.is_configured,
        "webhook_configured": provider.has_webhook_secret,
    }


@router.post("/razorpayx/payouts")
async def razorpayx_create_payout(
    db: DbSession, current_user: CurrentUserDep, settings: AppSettings
) -> dict:
    await require_permission(db, current_user, "finance.admin")
    provider = build_payout_provider(settings)
    try:
        result = await provider.create_payout(
            account_number="", ifsc="", amount_paise=0, purpose="", reference_id=""
        )
    except RazorpayXNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"payout_id": result.payout_id, "status": result.status}


@router.get("/razorpayx/balance")
async def razorpayx_balance(
    db: DbSession, current_user: CurrentUserDep, settings: AppSettings
) -> dict:
    await _require_finance(db, current_user, "finance.accounts.read")
    provider = build_payout_provider(settings)
    try:
        result = await provider.fetch_balance()
    except RazorpayXNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"balance_paise": result.balance_paise, "currency": result.currency}


@router.post("/razorpayx/webhook", status_code=status.HTTP_202_ACCEPTED)
async def razorpayx_webhook(request: Request, settings: AppSettings) -> dict:
    """Verifies the RazorpayX webhook signature when a secret is configured;
    otherwise rejects. No processing is implemented yet (placeholder seam)."""
    provider = build_payout_provider(settings)
    if not provider.has_webhook_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RazorpayX webhook secret is not configured.",
        )
    signature = request.headers.get("X-Razorpay-Signature", "")
    body = await request.body()
    if not signature or not provider.verify_webhook(body, signature):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature."
        )
    return {"status": "accepted"}
