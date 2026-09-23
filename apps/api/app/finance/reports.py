"""Read-only reports, all derived from the journal (fin_journal_lines).

Every report here is a pure aggregation query — nothing writes. Amounts are
paise integers; callers format for display/CSV.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance.ledger import fy_bounds
from app.finance.models import Donation, Donor, JournalEntry, JournalLine, LedgerAccount


async def trial_balance(db: AsyncSession, fy_label: str | None = None) -> list[dict]:
    """One row per account with nonzero activity: total debits, total
    credits, and the signed balance in the account's normal-balance sense.
    Summed across all rows, debit_total - credit_total is always zero for a
    consistent ledger (every entry is balanced at posting time).
    """
    stmt = (
        select(
            LedgerAccount.id,
            LedgerAccount.code,
            LedgerAccount.name,
            LedgerAccount.account_type,
            LedgerAccount.normal_balance,
            func.coalesce(func.sum(JournalLine.debit_paise), 0),
            func.coalesce(func.sum(JournalLine.credit_paise), 0),
        )
        .join(JournalLine, JournalLine.account_id == LedgerAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .group_by(
            LedgerAccount.id,
            LedgerAccount.code,
            LedgerAccount.name,
            LedgerAccount.account_type,
            LedgerAccount.normal_balance,
        )
        .order_by(LedgerAccount.code)
    )
    if fy_label:
        stmt = stmt.where(JournalEntry.fy_label == fy_label)
    rows = (await db.execute(stmt)).all()
    out = []
    for (
        account_id,
        code,
        name,
        account_type,
        normal_balance,
        debit_total,
        credit_total,
    ) in rows:
        balance = (
            (debit_total - credit_total)
            if normal_balance == "debit"
            else (credit_total - debit_total)
        )
        out.append(
            {
                "account_id": str(account_id),
                "code": code,
                "name": name,
                "account_type": account_type,
                "debit_total_paise": int(debit_total),
                "credit_total_paise": int(credit_total),
                "balance_paise": int(balance),
            }
        )
    return out


async def income_expenditure(db: AsyncSession, fy_label: str) -> dict:
    rows = await trial_balance(db, fy_label)
    income = [r for r in rows if r["account_type"] == "income"]
    expense = [r for r in rows if r["account_type"] == "expense"]
    total_income = sum(r["balance_paise"] for r in income)
    total_expense = sum(r["balance_paise"] for r in expense)
    return {
        "fy_label": fy_label,
        "income": income,
        "expense": expense,
        "total_income_paise": total_income,
        "total_expense_paise": total_expense,
        "surplus_deficit_paise": total_income - total_expense,
    }


async def balance_sheet(db: AsyncSession, as_of_fy: str | None = None) -> dict:
    """Schedule-III-ish grouping: Assets / Liabilities / Equity (Funds), cumulative
    since inception through the end of ``as_of_fy`` (or all time if omitted)."""
    stmt = (
        select(
            LedgerAccount.id,
            LedgerAccount.code,
            LedgerAccount.name,
            LedgerAccount.account_type,
            LedgerAccount.normal_balance,
            func.coalesce(func.sum(JournalLine.debit_paise), 0),
            func.coalesce(func.sum(JournalLine.credit_paise), 0),
        )
        .join(JournalLine, JournalLine.account_id == LedgerAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .group_by(
            LedgerAccount.id,
            LedgerAccount.code,
            LedgerAccount.name,
            LedgerAccount.account_type,
            LedgerAccount.normal_balance,
        )
        .order_by(LedgerAccount.code)
    )
    if as_of_fy:
        _, end = fy_bounds(as_of_fy)
        stmt = stmt.where(JournalEntry.entry_date <= end)
    rows = (await db.execute(stmt)).all()

    def bucket(account_type: str) -> list[dict]:
        result = []
        for (
            account_id,
            code,
            name,
            a_type,
            normal_balance,
            debit_total,
            credit_total,
        ) in rows:
            if a_type != account_type:
                continue
            balance = (
                (debit_total - credit_total)
                if normal_balance == "debit"
                else (credit_total - debit_total)
            )
            if balance == 0:
                continue
            result.append(
                {
                    "account_id": str(account_id),
                    "code": code,
                    "name": name,
                    "balance_paise": int(balance),
                }
            )
        return result

    assets, liabilities, equity = bucket("asset"), bucket("liability"), bucket("equity")
    total_assets = sum(r["balance_paise"] for r in assets)
    total_liabilities = sum(r["balance_paise"] for r in liabilities)
    total_equity = sum(r["balance_paise"] for r in equity)
    return {
        "as_of_fy": as_of_fy,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets_paise": total_assets,
        "total_liabilities_paise": total_liabilities,
        "total_equity_paise": total_equity,
        # Balance sheet identity check: Assets == Liabilities + Equity
        "balanced": total_assets == (total_liabilities + total_equity),
    }


async def receipts_and_payments(db: AsyncSession, fy_label: str) -> list[dict]:
    """Cash-basis view: every journal line touching Bank (1001) or Cash (1002)
    within the FY, with its counterparty account."""
    cash_codes = ("1001", "1002")
    stmt = (
        select(
            JournalEntry.entry_date,
            LedgerAccount.code,
            JournalLine.debit_paise,
            JournalLine.credit_paise,
            JournalLine.description,
            JournalEntry.memo,
        )
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(LedgerAccount, LedgerAccount.id == JournalLine.account_id)
        .where(JournalEntry.fy_label == fy_label, LedgerAccount.code.in_(cash_codes))
        .order_by(JournalEntry.entry_date)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "date": entry_date.isoformat(),
            "cash_account": code,
            "receipt_paise": int(debit_paise),
            "payment_paise": int(credit_paise),
            "narration": description or memo,
        }
        for entry_date, code, debit_paise, credit_paise, description, memo in rows
    ]


async def general_ledger(
    db: AsyncSession, account_id: uuid.UUID, fy_label: str | None = None
) -> list[dict]:
    account = await db.get(LedgerAccount, account_id)
    if account is None:
        return []
    stmt = (
        select(
            JournalEntry.entry_date,
            JournalEntry.memo,
            JournalLine.debit_paise,
            JournalLine.credit_paise,
            JournalLine.description,
        )
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account_id)
        .order_by(JournalEntry.entry_date, JournalEntry.posted_at)
    )
    if fy_label:
        stmt = stmt.where(JournalEntry.fy_label == fy_label)
    rows = (await db.execute(stmt)).all()
    running = 0
    out = []
    for entry_date, memo, debit_paise, credit_paise, description in rows:
        delta = (
            (debit_paise - credit_paise)
            if account.normal_balance == "debit"
            else (credit_paise - debit_paise)
        )
        running += delta
        out.append(
            {
                "date": entry_date.isoformat(),
                "narration": description or memo,
                "debit_paise": int(debit_paise),
                "credit_paise": int(credit_paise),
                "running_balance_paise": int(running),
            }
        )
    return out


async def donor_report(db: AsyncSession, fy_label: str | None = None) -> list[dict]:
    stmt = (
        select(
            Donor.name,
            Donor.pan,
            Donor.donor_type,
            func.count(Donation.id),
            func.coalesce(func.sum(Donation.amount_paise), 0),
        )
        .join(Donation, Donation.donor_id == Donor.id)
        .where(Donation.status == "confirmed")
        .group_by(Donor.id, Donor.name, Donor.pan, Donor.donor_type)
        .order_by(Donor.name)
    )
    if fy_label:
        stmt = stmt.where(Donation.fy_label == fy_label)
    rows = (await db.execute(stmt)).all()
    return [
        {
            "donor_name": name,
            "pan": pan,
            "donor_type": donor_type,
            "donation_count": int(count),
            "total_paise": int(total),
        }
        for name, pan, donor_type, count, total in rows
    ]


async def form10bd_rows(db: AsyncSession, fy_label: str) -> list[dict]:
    """Form 10BD (statement of donations, Income-tax Rules, r.18AB) column set."""
    stmt = (
        select(
            Donor.name,
            Donor.pan,
            Donor.address,
            Donation.mode,
            Donation.donation_date,
            Donation.amount_paise,
            Donation.receipt_number,
        )
        .join(Donation, Donation.donor_id == Donor.id)
        .where(
            Donation.status == "confirmed",
            Donation.fy_label == fy_label,
            Donation.claim_80g.is_(True),
        )
        .order_by(Donation.donation_date)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "donor_name": name,
            "unique_identification_number": pan or "",
            "address": address or "",
            "type_of_donation": "Corpus" if False else "Specific/Other",
            "mode_of_receipt": mode,
            "date": donation_date.isoformat(),
            "amount_paise": int(amount_paise),
            "receipt_number": receipt_number,
        }
        for name, pan, address, mode, donation_date, amount_paise, receipt_number in rows
    ]


async def tds_quarterly(db: AsyncSession, fy_label: str, quarter: int) -> list[dict]:
    from app.finance.models import Bill, Vendor

    q_months = {1: (4, 5, 6), 2: (7, 8, 9), 3: (10, 11, 12), 4: (1, 2, 3)}[quarter]
    stmt = (
        select(
            Vendor.name,
            Vendor.pan,
            Bill.tds_section,
            Bill.tds_rate_bps,
            Bill.amount_paise,
            Bill.tds_amount_paise,
            Bill.bill_date,
        )
        .join(Bill, Bill.vendor_id == Vendor.id)
        .where(Bill.fy_label == fy_label, Bill.tds_section.is_not(None))
        .order_by(Bill.bill_date)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "vendor_name": name,
            "pan": pan or "",
            "section": section,
            "rate_percent": (rate_bps or 0) / 100,
            "bill_amount_paise": int(amount_paise),
            "tds_amount_paise": int(tds_amount_paise),
            "bill_date": bill_date.isoformat(),
        }
        for name, pan, section, rate_bps, amount_paise, tds_amount_paise, bill_date in rows
        if bill_date.month in q_months
    ]
