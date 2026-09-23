"""
SQLAlchemy 2.0 ORM models for the Finance Ledger subsystem.

All tables are prefixed ``fin_`` and share ``app.db.models.Base`` so they live
in the same metadata / migration stream as the rest of the platform. This
module is imported (for its Base.metadata side effects) from
``apps/api/alembic/env.py`` and — transitively, via the router import in
``app.main`` — before any test creates tables from ``Base.metadata``.

Design summary (docs/finance_ledger_design.md):
    * ``LedgerAccount`` / ``JournalEntry`` / ``JournalLine`` form an immutable
      double-entry ledger. Postings are append-only; corrections are made by
      posting a reversal entry (see app.finance.ledger.reverse_journal_entry),
      never by UPDATE/DELETE of a posted entry or line.
    * ``FiscalPeriod`` gates postings to a financial year (1 Apr – 31 Mar);
      once closed, no new entry may be dated inside it.
    * ``Voucher`` is the maker-checker unit for payments/receipts/journals —
      it carries a sequential, gap-free number allocated only at approval
      time (never at draft creation, so abandoned drafts don't burn numbers).
    * ``Donor``/``Donation`` and ``Vendor``/``Bill`` are the donation and
      payables sub-ledgers; both post into the same journal.
    * ``FinOrgSettings`` is a single-row table holding the Foundation's legal
      registration numbers (80G, 12A, FCRA, PAN, TAN, GSTIN) as *settings* —
      nothing here is invented; fields default to NULL until entered.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base

# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------


class LedgerAccount(Base):
    """A node in the chart of accounts (assets/liabilities/equity/income/expense)."""

    __tablename__ = "fin_ledger_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('asset','liability','equity','income','expense')",
            name="ck_fin_ledger_accounts_type",
        ),
        CheckConstraint(
            "normal_balance IN ('debit','credit')",
            name="ck_fin_ledger_accounts_normal_balance",
        ),
        CheckConstraint(
            "fund_type IN ('unrestricted','restricted','na')",
            name="ck_fin_ledger_accounts_fund_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # 'asset' | 'liability' | 'equity' | 'income' | 'expense'
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'debit' | 'credit' — the side that increases this account's balance
    normal_balance: Mapped[str] = mapped_column(String(6), nullable=False)
    # 'unrestricted' | 'restricted' | 'na' — fund accounting split (donor-restricted funds)
    fund_type: Mapped[str] = mapped_column(
        String(20), default="unrestricted", nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # System-seeded accounts (chart of accounts, per-virtual-account fund nodes) are
    # protected from deletion via the API; only is_active may be toggled.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<LedgerAccount {self.code} {self.name!r}>"


# ---------------------------------------------------------------------------
# Journal — append-only double entry
# ---------------------------------------------------------------------------


class JournalEntry(Base):
    """An append-only, balanced double-entry posting.

    Never updated or deleted. A correction is made by posting a new entry
    with ``reverses_entry_id`` set to this entry's id (see
    app.finance.ledger.reverse_journal_entry); the original row is untouched.
    """

    __tablename__ = "fin_journal_entries"
    __table_args__ = (
        Index("ix_fin_journal_entries_fy", "fy_label"),
        Index("ix_fin_journal_entries_entry_date", "entry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[str] = mapped_column(Text, nullable=False)
    # 'voucher' | 'donation' | 'bill' | 'money_request' | 'card_charge' | 'opening_balance' | 'reversal'
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    reverses_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    posted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_no",
    )

    def __repr__(self) -> str:
        return f"<JournalEntry id={self.id} fy={self.fy_label!r} source={self.source_type!r}>"


class JournalLine(Base):
    """One leg of a journal entry. Exactly one of debit/credit is nonzero."""

    __tablename__ = "fin_journal_lines"
    __table_args__ = (
        CheckConstraint(
            "debit_paise >= 0 AND credit_paise >= 0 "
            "AND NOT (debit_paise > 0 AND credit_paise > 0) "
            "AND (debit_paise > 0 OR credit_paise > 0)",
            name="ck_fin_journal_lines_single_side",
        ),
        Index("ix_fin_journal_lines_account", "account_id"),
        Index("ix_fin_journal_lines_project_tag", "project_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    debit_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credit_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Fork/city/project tag for budget-vs-actuals reporting (free text code, e.g. "delhi")
    project_tag: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fund_type: Mapped[str] = mapped_column(
        String(20), default="unrestricted", nullable=False
    )

    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["LedgerAccount"] = relationship("LedgerAccount")

    def __repr__(self) -> str:
        return f"<JournalLine entry={self.entry_id} account={self.account_id} dr={self.debit_paise} cr={self.credit_paise}>"


# ---------------------------------------------------------------------------
# Fiscal periods (1 April – 31 March)
# ---------------------------------------------------------------------------


class FiscalPeriod(Base):
    """One row per financial year. Closing a period blocks further postings into it."""

    __tablename__ = "fin_fiscal_periods"
    __table_args__ = (UniqueConstraint("fy_label", name="uq_fin_fiscal_periods_fy"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opening_balances_posted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<FiscalPeriod {self.fy_label} closed={self.is_closed}>"


# ---------------------------------------------------------------------------
# Sequential, gap-free numbering
# ---------------------------------------------------------------------------


class VoucherCounter(Base):
    """A per-(FY, document type) counter. Incremented under a row lock so
    numbers allocated at approval time are sequential and gap-free."""

    __tablename__ = "fin_voucher_counters"
    __table_args__ = (
        UniqueConstraint(
            "fy_label", "series", name="uq_fin_voucher_counters_fy_series"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    # 'PV' | 'RV' | 'JV' | 'DR' (payment / receipt / journal voucher, donation receipt)
    series: Mapped[str] = mapped_column(String(10), nullable=False)
    next_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# ---------------------------------------------------------------------------
# Vouchers & attachments
# ---------------------------------------------------------------------------


class Voucher(Base):
    """Payment / receipt / journal voucher — the maker-checker unit for money movement.

    ``voucher_number`` is allocated only when the voucher is approved and
    posted (never at draft creation), so a rejected or abandoned draft never
    burns a sequence number.
    """

    __tablename__ = "fin_vouchers"
    __table_args__ = (
        CheckConstraint(
            "voucher_type IN ('payment','receipt','journal')",
            name="ck_fin_vouchers_type",
        ),
        CheckConstraint(
            "status IN ('draft','pending_approval','approved','rejected','posted','void')",
            name="ck_fin_vouchers_status",
        ),
        Index("ix_fin_vouchers_status", "status"),
        Index("ix_fin_vouchers_fy", "fy_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    voucher_type: Mapped[str] = mapped_column(String(10), nullable=False)
    voucher_number: Mapped[str | None] = mapped_column(
        String(40), nullable=True, unique=True
    )
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    narration: Mapped[str] = mapped_column(Text, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    debit_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    credit_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # 'vendor' | 'donor' | None
    party_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    party_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_bills.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 'cash' | 'upi' | 'bank_transfer' | 'cheque' | 'card'
    payment_mode: Mapped[str] = mapped_column(
        String(20), default="bank_transfer", nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Voucher {self.voucher_number or '(unnumbered)'} status={self.status!r}>"
        )


class FinDocument(Base):
    """Supporting document attached to a voucher, donation, or bill."""

    __tablename__ = "fin_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    voucher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_vouchers.id", ondelete="CASCADE"),
        nullable=True,
    )
    donation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_donations.id", ondelete="CASCADE"),
        nullable=True,
    )
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_bills.id", ondelete="CASCADE"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Donors & donations
# ---------------------------------------------------------------------------


class Donor(Base):
    __tablename__ = "fin_donors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 'individual' | 'huf' | 'company' | 'trust' | 'foreign' | 'other'
    donor_type: Mapped[str] = mapped_column(
        String(20), default="individual", nullable=False
    )
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    # FCRA guard input: a donation from a foreign-source donor is blocked unless
    # FinOrgSettings.fcra_registration_no is set (Foreign Contribution
    # (Regulation) Act, 2010, s.6).
    is_foreign_source: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Donor {self.name!r} foreign={self.is_foreign_source}>"


class Donation(Base):
    """A donation. ``receipt_number`` and the journal posting only happen at
    confirmation (maker-checker: the confirmer may not be the recorder)."""

    __tablename__ = "fin_donations"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('cash','upi','bank_transfer','cheque','card','in_kind')",
            name="ck_fin_donations_mode",
        ),
        CheckConstraint(
            "status IN ('recorded','confirmed','rejected')",
            name="ck_fin_donations_status",
        ),
        Index("ix_fin_donations_fy", "fy_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    donor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_donors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receipt_number: Mapped[str | None] = mapped_column(
        String(40), nullable=True, unique=True
    )
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    donation_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_restricted_fund: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    claim_80g: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="recorded", nullable=False)
    voucher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_vouchers.id", ondelete="SET NULL"),
        nullable=True,
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    donor: Mapped["Donor"] = relationship("Donor")

    def __repr__(self) -> str:
        return f"<Donation {self.receipt_number or '(unconfirmed)'} amount={self.amount_paise}>"


# ---------------------------------------------------------------------------
# Vendors, bills & TDS
# ---------------------------------------------------------------------------


class Vendor(Base):
    __tablename__ = "fin_vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Bill(Base):
    """A vendor bill (accrual). Posts Debit Expense / Credit Payable (net of TDS)
    + Credit TDS Payable at creation; a linked payment Voucher later clears the
    payable against Bank/Cash."""

    __tablename__ = "fin_bills"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unpaid','paid','partial')", name="ck_fin_bills_status"
        ),
        Index("ix_fin_bills_fy", "fy_label"),
        Index("ix_fin_bills_vendor", "vendor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_vendors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bill_number: Mapped[str] = mapped_column(String(60), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    expense_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # TDS (Income-tax Act, 1961 Chapter XVII-B), e.g. '194C', '194J'
    tds_section: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tds_rate_bps: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # basis points; 1000 = 10%
    tds_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gst_input_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vendor: Mapped["Vendor"] = relationship("Vendor")

    def __repr__(self) -> str:
        return f"<Bill {self.bill_number} vendor={self.vendor_id} amount={self.amount_paise}>"


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


class Budget(Base):
    __tablename__ = "fin_budgets"
    __table_args__ = (
        UniqueConstraint(
            "fy_label",
            "account_id",
            "project_tag",
            name="uq_fin_budgets_fy_account_project",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fy_label: Mapped[str] = mapped_column(String(7), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_tag: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    budgeted_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Bank reconciliation
# ---------------------------------------------------------------------------


class BankStatementLine(Base):
    __tablename__ = "fin_bank_statement_lines"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('debit','credit')", name="ck_fin_bank_lines_direction"
        ),
        CheckConstraint(
            "status IN ('unmatched','matched','ignored')",
            name="ck_fin_bank_lines_status",
        ),
        Index("ix_fin_bank_lines_batch", "batch_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_label: Mapped[str] = mapped_column(String(100), nullable=False)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unmatched", nullable=False)
    matched_journal_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_journal_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    imported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Virtual-account ↔ fund-account linkage (keeps virtual_accounts untouched)
# ---------------------------------------------------------------------------


class VirtualAccountFundLink(Base):
    """Maps a paper VirtualAccount (app.db.models.VirtualAccount) to its
    ledger fund account, so existing MoneyRequest/card-charge flows can post
    balanced journal entries without adding columns to virtual_accounts."""

    __tablename__ = "fin_virtual_account_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    virtual_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    ledger_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fin_ledger_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Organisation legal/registration settings (singleton)
# ---------------------------------------------------------------------------

ORG_SETTINGS_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class FinOrgSettings(Base):
    """Single-row table of legal registration numbers used by receipts and
    compliance guards. Every field defaults to NULL — nothing is invented;
    the CFO fills these in as registrations are obtained."""

    __tablename__ = "fin_org_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    income_tax_80g_reg_no: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    income_tax_80g_valid_upto: Mapped[date | None] = mapped_column(Date, nullable=True)
    income_tax_12a_reg_no: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    fcra_registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fcra_valid_upto: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, name="metadata", default=dict, nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
