"""Add the Finance Ledger subsystem (chart of accounts, journal, fiscal
periods, vouchers, donors/donations, vendors/bills, budgets, bank
reconciliation, virtual-account fund links, org legal settings).

Purely additive: 15 new ``fin_*`` tables, zero changes to any existing table
or column, so it is backward compatible with the running application during
rollout (per MEMORY.md's migration rule). The paper virtual-ledger tables
(virtual_accounts, virtual_cards, money_requests, virtual_transactions) are
untouched; app.finance.models.VirtualAccountFundLink is a side table that
maps a virtual_accounts row to its ledger fund account without adding a
column there.

The standard chart-of-accounts rows (Bank, Cash, Payables, Funds, Income,
Expense — see app.finance.ledger.SYSTEM_ACCOUNTS) are intentionally NOT
seeded by this migration. They are created lazily and idempotently by
``get_or_create_account`` on first use, so there is a single source of truth
for the chart of accounts (the code, not a frozen migration-time copy) and
this migration never risks drifting from it.

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "w7x8y9z0a1b2"
down_revision = "v6w7x8y9z0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Chart of accounts ---------------------------------------------------
    op.create_table(
        "fin_ledger_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("normal_balance", sa.String(length=6), nullable=False),
        sa.Column(
            "fund_type",
            sa.String(length=20),
            nullable=False,
            server_default="unrestricted",
        ),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["fin_ledger_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_fin_ledger_accounts_code"),
        sa.CheckConstraint(
            "account_type IN ('asset','liability','equity','income','expense')",
            name="ck_fin_ledger_accounts_type",
        ),
        sa.CheckConstraint(
            "normal_balance IN ('debit','credit')",
            name="ck_fin_ledger_accounts_normal_balance",
        ),
        sa.CheckConstraint(
            "fund_type IN ('unrestricted','restricted','na')",
            name="ck_fin_ledger_accounts_fund_type",
        ),
    )
    op.create_index("ix_fin_ledger_accounts_code", "fin_ledger_accounts", ["code"])

    # -- Journal (append-only double entry) ----------------------------------
    op.create_table(
        "fin_journal_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("reverses_entry_id", sa.UUID(), nullable=True),
        sa.Column("posted_by", sa.UUID(), nullable=True),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reverses_entry_id"], ["fin_journal_entries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fin_journal_entries_fy", "fin_journal_entries", ["fy_label"])
    op.create_index(
        "ix_fin_journal_entries_entry_date", "fin_journal_entries", ["entry_date"]
    )
    op.create_index(
        "ix_fin_journal_entries_source_id", "fin_journal_entries", ["source_id"]
    )

    op.create_table(
        "fin_journal_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entry_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debit_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_tag", sa.String(length=60), nullable=True),
        sa.Column(
            "fund_type",
            sa.String(length=20),
            nullable=False,
            server_default="unrestricted",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["fin_journal_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["fin_ledger_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "debit_paise >= 0 AND credit_paise >= 0 "
            "AND NOT (debit_paise > 0 AND credit_paise > 0) "
            "AND (debit_paise > 0 OR credit_paise > 0)",
            name="ck_fin_journal_lines_single_side",
        ),
    )
    op.create_index("ix_fin_journal_lines_account", "fin_journal_lines", ["account_id"])
    op.create_index(
        "ix_fin_journal_lines_project_tag", "fin_journal_lines", ["project_tag"]
    )

    # Defense-in-depth: a Postgres trigger that rejects any UPDATE/DELETE on
    # posted journal rows, so the append-only guarantee holds even against a
    # stray manual UPDATE/DELETE statement, not just disciplined app code.
    # Skipped on SQLite (no CREATE TRIGGER ... FOR EACH ROW / RAISE support in
    # the form used here; SQLite test databases are built from
    # Base.metadata.create_all, not this migration, anyway).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION fin_journal_immutable() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'fin_journal_entries/fin_journal_lines are append-only; post a reversal entry instead of %', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_fin_journal_entries_immutable
            BEFORE UPDATE OR DELETE ON fin_journal_entries
            FOR EACH ROW EXECUTE FUNCTION fin_journal_immutable();
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_fin_journal_lines_immutable
            BEFORE UPDATE OR DELETE ON fin_journal_lines
            FOR EACH ROW EXECUTE FUNCTION fin_journal_immutable();
            """
        )

    # -- Fiscal periods -------------------------------------------------------
    op.create_table(
        "fin_fiscal_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("closed_by", sa.UUID(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "opening_balances_posted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fy_label", name="uq_fin_fiscal_periods_fy"),
    )

    # -- Sequential numbering --------------------------------------------------
    op.create_table(
        "fin_voucher_counters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fy_label", "series", name="uq_fin_voucher_counters_fy_series"
        ),
    )

    # -- Vendors & bills --------------------------------------------------------
    op.create_table(
        "fin_vendors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("pan", sa.String(length=10), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "fin_bills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=False),
        sa.Column("bill_number", sa.String(length=60), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("expense_account_id", sa.UUID(), nullable=True),
        sa.Column("tds_section", sa.String(length=10), nullable=True),
        sa.Column("tds_rate_bps", sa.Integer(), nullable=True),
        sa.Column("tds_amount_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gst_input_paise", sa.Integer(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="unpaid"
        ),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vendor_id"], ["fin_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["expense_account_id"], ["fin_ledger_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["fin_journal_entries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('unpaid','paid','partial')", name="ck_fin_bills_status"
        ),
    )
    op.create_index("ix_fin_bills_fy", "fin_bills", ["fy_label"])
    op.create_index("ix_fin_bills_vendor", "fin_bills", ["vendor_id"])

    # -- Vouchers & attachments ---------------------------------------------
    op.create_table(
        "fin_vouchers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("voucher_type", sa.String(length=10), nullable=False),
        sa.Column("voucher_number", sa.String(length=40), nullable=True),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("debit_account_id", sa.UUID(), nullable=True),
        sa.Column("credit_account_id", sa.UUID(), nullable=True),
        sa.Column("party_type", sa.String(length=20), nullable=True),
        sa.Column("party_id", sa.UUID(), nullable=True),
        sa.Column("bill_id", sa.UUID(), nullable=True),
        sa.Column(
            "payment_mode",
            sa.String(length=20),
            nullable=False,
            server_default="bank_transfer",
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="draft"
        ),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["debit_account_id"], ["fin_ledger_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["credit_account_id"], ["fin_ledger_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["bill_id"], ["fin_bills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["fin_journal_entries.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("voucher_number", name="uq_fin_vouchers_number"),
        sa.CheckConstraint(
            "voucher_type IN ('payment','receipt','journal')",
            name="ck_fin_vouchers_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','pending_approval','approved','rejected','posted','void')",
            name="ck_fin_vouchers_status",
        ),
    )
    op.create_index("ix_fin_vouchers_status", "fin_vouchers", ["status"])
    op.create_index("ix_fin_vouchers_fy", "fin_vouchers", ["fy_label"])

    # -- Donors & donations ---------------------------------------------------
    op.create_table(
        "fin_donors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "donor_type",
            sa.String(length=20),
            nullable=False,
            server_default="individual",
        ),
        sa.Column("pan", sa.String(length=10), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="IN"),
        sa.Column(
            "is_foreign_source", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "fin_donations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("donor_id", sa.UUID(), nullable=False),
        sa.Column("receipt_number", sa.String(length=40), nullable=True),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("donation_date", sa.Date(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=True),
        sa.Column(
            "is_restricted_fund",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("claim_80g", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="recorded"
        ),
        sa.Column("voucher_id", sa.UUID(), nullable=True),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("confirmed_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["donor_id"], ["fin_donors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["voucher_id"], ["fin_vouchers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["fin_journal_entries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_number", name="uq_fin_donations_receipt_number"),
        sa.CheckConstraint(
            "mode IN ('cash','upi','bank_transfer','cheque','card','in_kind')",
            name="ck_fin_donations_mode",
        ),
        sa.CheckConstraint(
            "status IN ('recorded','confirmed','rejected')",
            name="ck_fin_donations_status",
        ),
    )
    op.create_index("ix_fin_donations_fy", "fin_donations", ["fy_label"])

    # -- Supporting documents ---------------------------------------------------
    op.create_table(
        "fin_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("voucher_id", sa.UUID(), nullable=True),
        sa.Column("donation_id", sa.UUID(), nullable=True),
        sa.Column("bill_id", sa.UUID(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["voucher_id"], ["fin_vouchers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["donation_id"], ["fin_donations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["bill_id"], ["fin_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- Budgets ----------------------------------------------------------------
    op.create_table(
        "fin_budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fy_label", sa.String(length=7), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column(
            "project_tag", sa.String(length=60), nullable=False, server_default=""
        ),
        sa.Column("budgeted_paise", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["fin_ledger_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fy_label",
            "account_id",
            "project_tag",
            name="uq_fin_budgets_fy_account_project",
        ),
    )

    # -- Bank reconciliation ------------------------------------------------
    op.create_table(
        "fin_bank_statement_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("batch_label", sa.String(length=100), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=6), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="unmatched"
        ),
        sa.Column("matched_journal_line_id", sa.UUID(), nullable=True),
        sa.Column("imported_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["matched_journal_line_id"], ["fin_journal_lines.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "direction IN ('debit','credit')", name="ck_fin_bank_lines_direction"
        ),
        sa.CheckConstraint(
            "status IN ('unmatched','matched','ignored')",
            name="ck_fin_bank_lines_status",
        ),
    )
    op.create_index(
        "ix_fin_bank_lines_batch", "fin_bank_statement_lines", ["batch_label"]
    )

    # -- Virtual account <-> fund account linkage ----------------------------
    op.create_table(
        "fin_virtual_account_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("virtual_account_id", sa.UUID(), nullable=False),
        sa.Column("ledger_account_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["virtual_account_id"], ["virtual_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ledger_account_id"], ["fin_ledger_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "virtual_account_id", name="uq_fin_virtual_account_links_account"
        ),
    )

    # -- Legal/registration settings (singleton) -----------------------------
    op.create_table(
        "fin_org_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pan", sa.String(length=10), nullable=True),
        sa.Column("tan", sa.String(length=10), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("income_tax_80g_reg_no", sa.String(length=100), nullable=True),
        sa.Column("income_tax_80g_valid_upto", sa.Date(), nullable=True),
        sa.Column("income_tax_12a_reg_no", sa.String(length=100), nullable=True),
        sa.Column("fcra_registration_no", sa.String(length=100), nullable=True),
        sa.Column("fcra_valid_upto", sa.Date(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_fin_journal_lines_immutable ON fin_journal_lines;"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_fin_journal_entries_immutable ON fin_journal_entries;"
        )
        op.execute("DROP FUNCTION IF EXISTS fin_journal_immutable();")

    op.drop_table("fin_org_settings")
    op.drop_table("fin_virtual_account_links")
    op.drop_table("fin_bank_statement_lines")
    op.drop_table("fin_budgets")
    op.drop_table("fin_documents")
    op.drop_table("fin_donations")
    op.drop_table("fin_donors")
    op.drop_table("fin_vouchers")
    op.drop_table("fin_bills")
    op.drop_table("fin_vendors")
    op.drop_table("fin_voucher_counters")
    op.drop_table("fin_fiscal_periods")
    op.drop_table("fin_journal_lines")
    op.drop_table("fin_journal_entries")
    op.drop_table("fin_ledger_accounts")
