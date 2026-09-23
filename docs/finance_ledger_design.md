# Design Document: Virtual Ledger & Card Transaction Simulation System

## Overview

This specification details the design for the internal virtual ledger and simulated transaction card system for the GOBITSNBYTES FOUNDATION. All transactions and balances are managed on paper; a single current account underpins the actual foundation operations.

---

## 1. Database Schema Extensions

### 1.1 `VirtualTransaction` (New Model)
A ledger of all debits and credits between virtual accounts or from the treasury pool.

```python
class VirtualTransaction(Base):
    __tablename__ = "virtual_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Null represents the main treasury pool
    source_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    destination_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'money_request' | 'card_charge' | 'manual_adjustment'
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### 1.2 `VirtualCard` (Modified Model)
We add columns to track daily and monthly spending limits for card simulation checks:

* `daily_limit_paise`: `Mapped[int | None]` (default `None`, meaning unlimited)
* `monthly_limit_paise`: `Mapped[int | None]` (default `None`, meaning unlimited)

---

## 2. API Endpoints

### 2.1 Get Account Transaction Ledger
* **Route**: `GET /api/finance/accounts/{account_id}/transactions`
* **Permission**: `finance.accounts.read`
* **Response**: List of transactions where the account is either the source or destination.
* **Pagination**: Supports query params `limit` and `offset`.

### 2.2 Card Charge Simulation
* **Route**: `POST /api/finance/cards/{card_id}/simulate-charge`
* **Permission**: `finance.cards.manage` (or matching card holder user-id check)
* **Payload**:
  ```json
  {
    "amount_paise": 150000,
    "merchant": "Amazon Web Services",
    "description": "Virtual cloud hosting fees"
  }
  ```
* **Validation & Execution**:
  1. Fetch `VirtualCard` and check `is_active` status.
  2. Fetch parent `VirtualAccount` and check balance: `balance_paise >= amount_paise`.
  3. Validate card limits:
     - Sum existing card charges in the last 24 hours plus new charge must not exceed `daily_limit_paise`.
     - Sum existing card charges in the current calendar month plus new charge must not exceed `monthly_limit_paise`.
  4. Perform atomic update in DB transaction block:
     - Create a `VirtualTransaction` entry with type `'card_charge'`.
     - Decrement parent `VirtualAccount.balance_paise` by `amount_paise`.
     - Return status `200 OK` with simulated transaction details.

### 2.3 Modify Money Request Approval
* When a money request is approved:
  - Create a corresponding `VirtualTransaction` entry.
  - Increment/decrement the respective account balances atomically.

---

## 3. Frontend Portal Upgrades

### 3.1 Account Details (`/finance/accounts/[id]`)
- Render a paginated **Transaction Ledger** showing historical debits/credits.
- Credits highlighted in green (`+₹X.XX`); debits highlighted in red/white (`-₹X.XX`).

### 3.2 Cards Dashboard (`/finance/cards`)
- Display daily and monthly limits on the card face.
- Add a **Simulate Card Charge** button/modal opening a slide-out drawer form.
- Form fields: Amount (in Rupees), Merchant Name, and Description.
- Shows instant feedback: success receipt or limit/balance decline error message.

### 3.3 Dashboard Feed (`/finance/dashboard`)
- List the most recent transactions foundation-wide (for finance admins) or user-owned accounts.

---

## 4. Finance Ledger Subsystem (built on top of the above)

The paper virtual ledger above (§1–3) is the internal transfer/card-simulation
layer. It now sits on top of a proper immutable double-entry ledger that
makes the Foundation's books legally sound for a Section 8 company under the
Companies Act, 2013. Everything is additive — `VirtualAccount`,
`VirtualCard`, `MoneyRequest`, `VirtualTransaction` and their endpoints are
unchanged; `app.finance.mapping` mirrors every money-request approval and
card charge onto the journal in the same DB transaction.

Code lives in `apps/api/app/finance/` (models, ledger, reports, compliance,
numbering, mapping, payout_provider, storage, schemas) and
`apps/api/app/routers/finance_ledger.py`. Migration:
`w7x8y9z0a1b2_add_finance_ledger.py` (15 new `fin_*` tables, purely
additive, no changes to existing tables).

### 4.1 Immutable double-entry journal
- Chart of accounts (`fin_ledger_accounts`): asset/liability/equity/income/expense,
  each with a `normal_balance` and a `fund_type` (`unrestricted`/`restricted`/`na`)
  for fund accounting. Standard accounts (Bank, Cash, Payables, TDS Payable,
  Treasury/Designated Funds, Donation Income, Program Expenses, …) are
  created idempotently on first use (`app.finance.ledger.get_or_create_account`)
  rather than seeded by the migration, so there is one source of truth.
  Each paper `VirtualAccount` gets its own fund account under "Designated
  Funds", linked via `fin_virtual_account_links` (no column added to
  `virtual_accounts`).
- `fin_journal_entries` / `fin_journal_lines`: every posting goes through
  `app.finance.ledger.post_journal_entry`, which rejects unbalanced entries
  (sum debit != sum credit) and postings into a closed financial year. A
  per-line DB CHECK constraint enforces exactly one of debit/credit is
  positive; on Postgres, `BEFORE UPDATE OR DELETE` triggers reject any
  mutation of a posted row outright (defense-in-depth beyond disciplined
  application code).
- **Corrections are reversal-only.** `app.finance.ledger.reverse_journal_entry`
  posts a new, mirror-image entry linked via `reverses_entry_id`; the
  original row is never touched. "Is this entry reversed?" is a derived
  query, not a stored/mutated flag.

### 4.2 Audit trail (Companies (Accounts) Rules, 2014, Rule 3(1))
- Every ledger/voucher/donation/period/settings action writes an
  `AuditLog` row via the existing `app.iam.audit.write_audit_entry` (append-only,
  no delete path exists anywhere in the codebase) — same mechanism as the
  rest of the platform. Combined with the append-only journal itself, the
  books carry a permanent edit trail with no hard-delete of financial records.

### 4.3 Financial years & period close
- FY = 1 April – 31 March (`app.finance.ledger.fy_label_for`/`fy_bounds`,
  matching the existing label format e.g. `"2026-27"`). `fin_fiscal_periods`
  gates postings: `POST /api/finance/periods/{fy}/close` blocks every further
  posting into that year (voucher approval, donation confirmation, bill
  booking, manual journal entries, and the money-request/card-charge journal
  mirror all call the same `assert_period_open` check).

### 4.4 Vouchers & documents
- `fin_vouchers`: payment/receipt/journal, maker-checker (`POST .../submit`
  by the creator, `POST .../approve` or `/reject` by someone else — 403 on
  self-approval). The sequential, gap-free `voucher_number`
  (`PV|RV|JV/<FY>/000001`) is allocated only at approval, via
  `app.finance.numbering.next_document_number` under a row lock — a
  rejected/abandoned draft never burns a number.
- `fin_documents`: supporting attachments, stored on the local filesystem
  under `FINANCE_STORAGE_DIR` (same pattern as
  `app.services.onboarding_documents`; never committed to git), with a
  20MB size cap, content-type allowlist, and SHA-256 recorded per file.

### 4.5 Donations & receipts
- `fin_donors` / `fin_donations`. Receipt numbers (`DR/<FY>/000001`) and the
  journal posting only happen on `POST /donations/{id}/confirm`, by a user
  other than the one who recorded it (maker-checker).
- **Cash receipt guard** (Income-tax Act, 1961, s.269ST): a cash donation
  ≥ ₹2,00,000 is rejected outright.
- **FCRA guard** (Foreign Contribution (Regulation) Act, 2010, s.6): a
  donation from a donor flagged `is_foreign_source` is blocked with 403
  unless `fin_org_settings.fcra_registration_no` is set.
- `claim_80g` requires the donor's PAN on file.
- `GET /api/finance/reports/form10bd?fy=` exports the Form 10BD (Income-tax
  Rules, r.18AB) column set as CSV.

### 4.6 Vendors, bills & TDS
- `fin_vendors` / `fin_bills`. Creating a bill books the accrual immediately
  (Debit Expense, Credit Payable net of TDS, Credit TDS Payable). TDS section/
  rate is entered per bill (reference table in `app.finance.compliance.TDS_SECTIONS`
  is a UI default, not a determination — confirm actual rates with the
  Foundation's CA). `POST /bills/{id}/pay` creates a **draft** payment
  voucher (net of TDS) that then goes through the normal voucher
  maker-checker flow — the endpoint itself never moves money.
- **Cash payment guard** (Income-tax Act, 1961, s.40A(3)): a cash payment
  > ₹10,000 is rejected.
- `GET /api/finance/reports/tds-quarterly?fy=&quarter=` exports a 26Q-style
  quarterly summary CSV grouped by vendor/section.

### 4.7 Budgets
- `fin_budgets`: per account + free-text project/city tag, per FY.
  `GET /budgets/vs-actuals?fy=` compares against the live trial balance.

### 4.8 Reports (all derived from the journal, all CSV-exportable)
- Trial balance, Income & Expenditure, Balance Sheet (Schedule III-ish
  asset/liability/equity grouping, with an explicit `balanced` check),
  Receipts & Payments (cash-basis, Bank/Cash account lines only), General
  Ledger per account (running balance), Donor report.

### 4.9 Bank reconciliation
- `POST /bank-rec/import` accepts a CSV (`date,description,amount_paise,direction`)
  into `fin_bank_statement_lines`; `POST /bank-rec/lines/{id}/match` links a
  line to a `fin_journal_lines` row, `/ignore` marks it out of scope.

### 4.10 RazorpayX payout seam (placeholder)
- `app.finance.payout_provider.PayoutProvider`: `create_payout` /
  `fetch_status` / `fetch_balance` / `verify_webhook`. The only
  implementation, `RazorpayXProvider`, makes zero network calls — every
  payout/balance method raises `RazorpayXNotConfigured` (surfaced as HTTP
  503), regardless of whether API keys are set. `POST /razorpayx/webhook`
  verifies an HMAC-SHA256 signature when `RAZORPAYX_WEBHOOK_SECRET` is
  configured and rejects everything (503) otherwise. Config keys:
  `RAZORPAYX_KEY_ID`, `RAZORPAYX_SECRET`, `RAZORPAYX_WEBHOOK_SECRET`
  (`apps/api/app/config.py`, `.env.example`) — this is distinct from the
  existing `app.services.razorpayx_adapter` seam, which only provisions
  paper `VirtualAccount`/`VirtualCard` identifiers.

### 4.11 Legal/registration settings
- `fin_org_settings` (single row): PAN, TAN, GSTIN, 12A registration, 80G
  registration + validity, FCRA registration + validity. Every field
  defaults to `NULL` — nothing is invented; the CFO fills each in once the
  Foundation actually holds it. `GET`/`PATCH /api/finance/settings/org`
  (`finance.settings.manage`).

### 4.12 Permissions
New IAM permission keys (seeded in `apps/api/app/db/seed.py`):
`finance.ledger.read`, `finance.ledger.post`, `finance.vouchers.read`,
`finance.vouchers.create`, `finance.vouchers.approve`,
`finance.donations.read`, `finance.donations.create`,
`finance.donations.approve`, `finance.vendors.read`, `finance.vendors.manage`,
`finance.budgets.read`, `finance.budgets.manage`, `finance.reports.read`,
`finance.bank_rec.manage`, `finance.settings.manage`. `finance.admin`
continues to supersede all of the above, matching the existing pattern.

### 4.13 Frontend
`apps/web/app/finance/{ledger,vouchers,donations,vendors,budgets,reports,
bank-reconciliation,settings}/page.tsx`, linked from `FinanceSidebar.tsx`.
Money is integer paise everywhere; `apps/web/lib/finance-format.ts` is the
one place that divides for display. Layouts are card-list based (no wide
data tables), so nothing needs a separate mobile treatment — the existing
375px-safe pattern from `/finance/requests` is reused throughout.
