"""Pydantic v2 request schemas for the Finance Ledger router.

Read/report endpoints return plain ``dict``/``list[dict]`` (see
app.finance.reports) — they're pure aggregation output, not domain state, so
a dedicated response model per report would just restate the dict keys.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class LedgerAccountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=150)
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    normal_balance: Literal["debit", "credit"]
    fund_type: Literal["unrestricted", "restricted", "na"] = "unrestricted"
    parent_code: str | None = None


class JournalLineCreate(BaseModel):
    account_id: uuid.UUID
    debit_paise: int = Field(0, ge=0)
    credit_paise: int = Field(0, ge=0)
    description: str | None = None
    project_tag: str | None = None
    fund_type: Literal["unrestricted", "restricted"] = "unrestricted"


class JournalEntryCreate(BaseModel):
    entry_date: date
    memo: str = Field(..., min_length=1)
    lines: list[JournalLineCreate] = Field(..., min_length=2)


class JournalEntryReverse(BaseModel):
    memo: str | None = None


class VoucherCreate(BaseModel):
    voucher_type: Literal["payment", "receipt", "journal"]
    voucher_date: date
    narration: str = Field(..., min_length=1)
    amount_paise: int = Field(..., gt=0)
    debit_account_id: uuid.UUID | None = None
    credit_account_id: uuid.UUID | None = None
    payment_mode: Literal["cash", "upi", "bank_transfer", "cheque", "card"] = (
        "bank_transfer"
    )
    party_type: Literal["vendor", "donor"] | None = None
    party_id: uuid.UUID | None = None
    bill_id: uuid.UUID | None = None


class VoucherReview(BaseModel):
    note: str | None = None


class DonorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    donor_type: Literal["individual", "huf", "company", "trust", "foreign", "other"] = (
        "individual"
    )
    pan: str | None = Field(None, max_length=10)
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str = "IN"
    is_foreign_source: bool = False


class DonationCreate(BaseModel):
    donor_id: uuid.UUID
    donation_date: date
    amount_paise: int = Field(..., gt=0)
    mode: Literal["cash", "upi", "bank_transfer", "cheque", "card", "in_kind"]
    purpose: str | None = None
    is_restricted_fund: bool = False
    claim_80g: bool = True


class VendorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    pan: str | None = Field(None, max_length=10)
    gstin: str | None = Field(None, max_length=15)
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    category: str | None = None


class BillCreate(BaseModel):
    vendor_id: uuid.UUID
    bill_number: str = Field(..., min_length=1, max_length=60)
    bill_date: date
    amount_paise: int = Field(..., gt=0)
    expense_account_id: uuid.UUID | None = None
    tds_section: str | None = None
    tds_rate_bps: int | None = Field(None, ge=0, le=10000)
    gst_input_paise: int | None = Field(None, ge=0)


class BillPay(BaseModel):
    payment_mode: Literal["cash", "upi", "bank_transfer", "cheque", "card"] = (
        "bank_transfer"
    )
    voucher_date: date | None = None


class BudgetCreate(BaseModel):
    fy_label: str
    account_id: uuid.UUID
    project_tag: str = ""
    budgeted_paise: int = Field(..., ge=0)
    notes: str | None = None


class BankStatementLineMatch(BaseModel):
    journal_line_id: uuid.UUID


class OrgSettingsUpdate(BaseModel):
    pan: str | None = None
    tan: str | None = None
    gstin: str | None = None
    income_tax_80g_reg_no: str | None = None
    income_tax_80g_valid_upto: date | None = None
    income_tax_12a_reg_no: str | None = None
    fcra_registration_no: str | None = None
    fcra_valid_upto: date | None = None
