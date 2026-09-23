"""Core double-entry ledger service.

Everything that touches money in the Finance system ultimately calls
``post_journal_entry`` (or ``reverse_journal_entry`` for a correction). Both
functions are the single choke point that enforces:

    * lines balance (sum(debit) == sum(credit)) before anything is written;
    * the target financial year's period is open (no postings into a closed
      period — Financial Year runs 1 April – 31 March);
    * posting is append-only — nothing here ever UPDATEs or DELETEs a
      previously posted JournalEntry/JournalLine row.

A per-line DB CHECK constraint (exactly one of debit/credit positive, see
app.finance.models.JournalLine) is defense-in-depth alongside the
application-level balance check.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VirtualAccount
from app.finance.models import (
    FiscalPeriod,
    JournalEntry,
    JournalLine,
    LedgerAccount,
    VirtualAccountFundLink,
)

# ---------------------------------------------------------------------------
# Financial year helpers (1 April – 31 March, matches app.routers.finance)
# ---------------------------------------------------------------------------


def fy_label_for(on: date) -> str:
    start_year = on.year if on.month >= 4 else on.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def fy_bounds(fy_label: str) -> tuple[date, date]:
    start_year = int(fy_label[:4])
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


async def get_or_create_period(db: AsyncSession, fy_label: str) -> FiscalPeriod:
    result = await db.execute(
        select(FiscalPeriod).where(FiscalPeriod.fy_label == fy_label)
    )
    period = result.scalar_one_or_none()
    if period is None:
        start, end = fy_bounds(fy_label)
        period = FiscalPeriod(fy_label=fy_label, start_date=start, end_date=end)
        db.add(period)
        await db.flush()
    return period


async def assert_period_open(db: AsyncSession, fy_label: str) -> None:
    period = await get_or_create_period(db, fy_label)
    if period.is_closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Financial year {fy_label} is closed for posting.",
        )


# ---------------------------------------------------------------------------
# Chart of accounts — idempotent get-or-create so it works whether or not the
# migration's seed data has run (e.g. SQLite test databases built straight
# from Base.metadata.create_all carry no migration data).
# ---------------------------------------------------------------------------

# (code, name, account_type, normal_balance, fund_type, parent_code)
SYSTEM_ACCOUNTS: list[tuple[str, str, str, str, str, str | None]] = [
    ("1001", "Bank — Foundation Current Account", "asset", "debit", "na", None),
    ("1002", "Cash in Hand", "asset", "debit", "na", None),
    ("1500", "GST Input Credit Receivable", "asset", "debit", "na", None),
    ("1900", "Sundry Debtors / Receivables", "asset", "debit", "na", None),
    ("2001", "Sundry Creditors / Payables", "liability", "credit", "na", None),
    ("2100", "TDS Payable", "liability", "credit", "na", None),
    ("2300", "Statutory Dues Payable", "liability", "credit", "na", None),
    ("3000", "Unallocated Treasury Fund", "equity", "credit", "unrestricted", None),
    (
        "3100",
        "Designated Funds (Unrestricted)",
        "equity",
        "credit",
        "unrestricted",
        None,
    ),
    ("3200", "Designated Funds (Restricted)", "equity", "credit", "restricted", None),
    (
        "3900",
        "Accumulated Surplus / Opening Balance Equity",
        "equity",
        "credit",
        "unrestricted",
        None,
    ),
    (
        "4000",
        "Donations & Grants — Unrestricted",
        "income",
        "credit",
        "unrestricted",
        None,
    ),
    ("4100", "Donations & Grants — Restricted", "income", "credit", "restricted", None),
    ("4200", "Sponsorship Income", "income", "credit", "unrestricted", None),
    ("4900", "Other Income", "income", "credit", "unrestricted", None),
    ("5000", "Program Expenses", "expense", "debit", "na", None),
    ("5100", "Event & Fork Expenses", "expense", "debit", "na", None),
    ("5200", "Administrative Expenses", "expense", "debit", "na", None),
    ("5300", "Employee & Contractor Costs", "expense", "debit", "na", None),
    ("5900", "Uncategorized / Card Charges", "expense", "debit", "na", None),
]


async def get_or_create_account(db: AsyncSession, code: str) -> LedgerAccount:
    """Get-or-create a well-known system account by its chart-of-accounts code."""
    result = await db.execute(select(LedgerAccount).where(LedgerAccount.code == code))
    account = result.scalar_one_or_none()
    if account is not None:
        return account

    spec = next((row for row in SYSTEM_ACCOUNTS if row[0] == code), None)
    if spec is None:
        raise ValueError(f"Unknown system ledger account code: {code!r}")
    _, name, account_type, normal_balance, fund_type, parent_code = spec
    parent_id = None
    if parent_code:
        parent = await get_or_create_account(db, parent_code)
        parent_id = parent.id
    account = LedgerAccount(
        code=code,
        name=name,
        account_type=account_type,
        normal_balance=normal_balance,
        fund_type=fund_type,
        parent_id=parent_id,
        is_system=True,
    )
    db.add(account)
    await db.flush()
    return account


async def ensure_system_accounts(db: AsyncSession) -> dict[str, LedgerAccount]:
    return {row[0]: await get_or_create_account(db, row[0]) for row in SYSTEM_ACCOUNTS}


async def get_or_create_fund_account(
    db: AsyncSession, virtual_account: VirtualAccount, *, restricted: bool = False
) -> LedgerAccount:
    """The ledger fund account that mirrors a VirtualAccount's paper balance."""
    result = await db.execute(
        select(VirtualAccountFundLink).where(
            VirtualAccountFundLink.virtual_account_id == virtual_account.id
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        account = await db.get(LedgerAccount, link.ledger_account_id)
        if account is not None:
            return account

    parent_code = "3200" if restricted else "3100"
    parent = await get_or_create_account(db, parent_code)
    # Deterministic, human-legible code: 39<8 hex chars of the virtual account id>
    code = f"39{virtual_account.id.hex[:8]}"
    fund_account = LedgerAccount(
        code=code,
        name=f"Designated Fund — {virtual_account.name}",
        account_type="equity",
        normal_balance="credit",
        fund_type="restricted" if restricted else "unrestricted",
        parent_id=parent.id,
        is_system=True,
    )
    db.add(fund_account)
    await db.flush()
    db.add(
        VirtualAccountFundLink(
            virtual_account_id=virtual_account.id, ledger_account_id=fund_account.id
        )
    )
    return fund_account


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JournalLineInput:
    account_id: uuid.UUID
    debit_paise: int = 0
    credit_paise: int = 0
    description: str | None = None
    project_tag: str | None = None
    fund_type: str = "unrestricted"


async def post_journal_entry(
    db: AsyncSession,
    *,
    entry_date: date,
    memo: str,
    lines: list[JournalLineInput],
    source_type: str,
    source_id: uuid.UUID | None = None,
    posted_by: uuid.UUID | None = None,
    reverses_entry_id: uuid.UUID | None = None,
) -> JournalEntry:
    """Post a balanced, append-only journal entry. Raises 400 if unbalanced,
    409 if the target financial year is closed."""
    if len(lines) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A journal entry needs at least two lines.",
        )
    total_debit = sum(line.debit_paise for line in lines)
    total_credit = sum(line.credit_paise for line in lines)
    if total_debit != total_credit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Journal entry is not balanced: debits={total_debit} credits={total_credit} (paise).",
        )
    if total_debit <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry amount must be positive.",
        )
    for line in lines:
        if (line.debit_paise > 0) == (line.credit_paise > 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each journal line must be either a debit or a credit, not both/neither.",
            )

    fy_label = fy_label_for(entry_date)
    await assert_period_open(db, fy_label)

    entry = JournalEntry(
        fy_label=fy_label,
        entry_date=entry_date,
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        posted_by=posted_by,
        reverses_entry_id=reverses_entry_id,
    )
    db.add(entry)
    await db.flush()

    for index, line in enumerate(lines):
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=line.account_id,
                line_no=index,
                debit_paise=line.debit_paise,
                credit_paise=line.credit_paise,
                description=line.description,
                project_tag=line.project_tag,
                fund_type=line.fund_type,
            )
        )
    await db.flush()
    return entry


async def reverse_journal_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    posted_by: uuid.UUID | None,
    memo: str | None = None,
    entry_date: date | None = None,
) -> JournalEntry:
    """Post the mirror-image entry that corrects ``entry_id``.

    The original entry is never modified — its lines are read and a brand
    new entry is posted with every debit/credit swapped, linked via
    ``reverses_entry_id``. Whether an entry "is reversed" is a derived fact
    (does any other entry reverse it?), not a stored/mutated flag.
    """
    result = await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
    original = result.scalar_one_or_none()
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found."
        )

    lines_result = await db.execute(
        select(JournalLine).where(JournalLine.entry_id == entry_id)
    )
    original_lines = list(lines_result.scalars().all())
    if not original_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry has no lines to reverse.",
        )

    reversal_lines = [
        JournalLineInput(
            account_id=line.account_id,
            debit_paise=line.credit_paise,
            credit_paise=line.debit_paise,
            description=f"Reversal: {line.description or ''}".strip(),
            project_tag=line.project_tag,
            fund_type=line.fund_type,
        )
        for line in original_lines
    ]
    return await post_journal_entry(
        db,
        entry_date=entry_date or datetime.now(timezone.utc).date(),
        memo=memo or f"Reversal of entry {entry_id}: {original.memo}",
        lines=reversal_lines,
        source_type="reversal",
        source_id=entry_id,
        posted_by=posted_by,
        reverses_entry_id=entry_id,
    )


async def is_entry_reversed(db: AsyncSession, entry_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(JournalEntry.id).where(JournalEntry.reverses_entry_id == entry_id)
    )
    return result.scalar_one_or_none() is not None
