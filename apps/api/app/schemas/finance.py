"""Pydantic v2 schemas for the Finance module (VirtualAccount, VirtualCard, MoneyRequest)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Virtual Account
# ---------------------------------------------------------------------------

class VirtualAccountCreate(BaseModel):
    """Schema for creating a new VirtualAccount."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    owner_id: uuid.UUID


class VirtualAccountUpdate(BaseModel):
    """Schema for updating an existing VirtualAccount."""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class VirtualAccountOut(BaseModel):
    """Schema representing a VirtualAccount returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    balance_paise: int
    # Convenience: expose balance in rupees as a float
    balance_rupees: float = 0.0
    account_number: str
    ifsc: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Validate and post-process balance_rupees conversion from paise."""
        instance = super().model_validate(obj, **kwargs)
        instance.balance_rupees = instance.balance_paise / 100
        return instance


# ---------------------------------------------------------------------------
# Virtual Card
# ---------------------------------------------------------------------------

class VirtualCardCreate(BaseModel):
    """Schema for issuing a new VirtualCard."""
    account_id: uuid.UUID
    holder_id: uuid.UUID
    card_name: str = Field(..., min_length=1, max_length=100)
    card_type: Literal["virtual", "debit"] = "virtual"
    expires_month: int = Field(..., ge=1, le=12)
    expires_year: int = Field(..., ge=2024, le=2040)
    daily_limit_paise: int | None = Field(None, ge=0)
    monthly_limit_paise: int | None = Field(None, ge=0)


class VirtualCardUpdate(BaseModel):
    """Schema for updating limits and status of a VirtualCard."""
    card_name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None
    daily_limit_paise: int | None = Field(None, ge=0)
    monthly_limit_paise: int | None = Field(None, ge=0)


class VirtualCardOut(BaseModel):
    """Schema representing a VirtualCard returned to the client with formatted fields."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    holder_id: uuid.UUID
    card_name: str
    last_four: str
    card_type: str
    is_active: bool
    expires_month: int
    expires_year: str = ""  # formatted "MM/YY" string
    daily_limit_paise: int | None
    monthly_limit_paise: int | None
    daily_limit_rupees: float | None = None
    monthly_limit_rupees: float | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def preprocess_data(cls, data: Any) -> Any:
        """Pre-processes SQLAlchemy objects or dictionaries to format fields like expiration date and limits."""
        # If it is a SQLAlchemy object or custom class
        if not isinstance(data, dict):
            yr = str(data.expires_year)[-2:] if hasattr(data, "expires_year") else "00"
            mo = f"{data.expires_month:02d}" if hasattr(data, "expires_month") else "00"
            
            daily = getattr(data, "daily_limit_paise", None)
            monthly = getattr(data, "monthly_limit_paise", None)
            
            return {
                "id": getattr(data, "id", None),
                "account_id": getattr(data, "account_id", None),
                "holder_id": getattr(data, "holder_id", None),
                "card_name": getattr(data, "card_name", None),
                "last_four": getattr(data, "last_four", None),
                "card_type": getattr(data, "card_type", None),
                "is_active": getattr(data, "is_active", None),
                "expires_month": getattr(data, "expires_month", None),
                "expires_year": f"{mo}/{yr}",
                "daily_limit_paise": daily,
                "monthly_limit_paise": monthly,
                "daily_limit_rupees": daily / 100 if daily is not None else None,
                "monthly_limit_rupees": monthly / 100 if monthly is not None else None,
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        else:
            # If it is a dict
            yr = str(data.get("expires_year", "00"))
            if "/" not in yr:
                yr_suffix = yr[-2:]
                mo = f"{data.get('expires_month', 0):02d}"
                data["expires_year"] = f"{mo}/{yr_suffix}"
            
            daily = data.get("daily_limit_paise")
            if daily is not None:
                data["daily_limit_rupees"] = daily / 100
            monthly = data.get("monthly_limit_paise")
            if monthly is not None:
                data["monthly_limit_rupees"] = monthly / 100
        return data


# ---------------------------------------------------------------------------
# Money Request
# ---------------------------------------------------------------------------

class MoneyRequestCreate(BaseModel):
    """Schema for submitting a money request."""
    # None = draw from main pool
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID
    amount_paise: int = Field(..., gt=0, description="Amount in paise (₹1 = 100 paise)")
    description: str = Field(..., min_length=1)


class MoneyRequestReview(BaseModel):
    """Schema for reviewing (approving/rejecting) a money request."""
    note: str | None = None


class MoneyRequestOut(BaseModel):
    """Schema representing a money request returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_account_id: uuid.UUID | None
    to_account_id: uuid.UUID
    requester_id: uuid.UUID
    amount_paise: int
    amount_rupees: float = 0.0
    description: str
    status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    # Dual authorization (OKF Rule 35): populated when the request amount is at
    # or above the configured threshold. approvals_count is the number of
    # DISTINCT approvers recorded so far; funds move only when it reaches
    # required_approvals.
    dual_approval_required: bool = False
    approvals_count: int = 0
    required_approvals: int = 2
    created_at: datetime
    updated_at: datetime

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Validate and post-process amount_rupees conversion from paise."""
        instance = super().model_validate(obj, **kwargs)
        instance.amount_rupees = instance.amount_paise / 100
        return instance


# ---------------------------------------------------------------------------
# Virtual Transaction & Simulation
# ---------------------------------------------------------------------------

class VirtualTransactionOut(BaseModel):
    """Schema representing a ledger transaction record returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_account_id: uuid.UUID | None
    destination_account_id: uuid.UUID | None
    amount_paise: int
    amount_rupees: float = 0.0
    reference_type: str
    reference_id: uuid.UUID | None
    description: str
    created_at: datetime

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Validate and post-process amount_rupees conversion from paise."""
        instance = super().model_validate(obj, **kwargs)
        instance.amount_rupees = instance.amount_paise / 100
        return instance


class CardSimulationPayload(BaseModel):
    """Schema for simulating a card authorization transaction."""
    amount_paise: int = Field(..., gt=0)
    merchant: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Section 8 & Chart of Accounts Schemas
# ---------------------------------------------------------------------------

class ChartOfAccountItem(BaseModel):
    """Schema for standard Section 8 Chart of Accounts classification."""
    code: str
    name: str
    account_type: Literal["asset", "liability", "equity", "revenue", "expense"]
    description: str
    section8_rules: str


class LedgerTransactionCreate(BaseModel):
    """Schema for posting a double-entry transaction to the ledger."""
    source_account_id: uuid.UUID | None = Field(None, description="Debit / Source Account ID")
    destination_account_id: uuid.UUID | None = Field(None, description="Credit / Destination Account ID")
    amount_paise: int = Field(..., gt=0, description="Amount in paise (₹1 = 100 paise)")
    category_code: str | None = Field(None, description="Chart of Accounts classification code (e.g. 5010)")
    description: str = Field(..., min_length=1, max_length=500)


class ExpenseReimbursementCreate(BaseModel):
    """Schema for submitting an expense reimbursement request under Section 8 rules."""
    to_account_id: uuid.UUID = Field(..., description="Target Virtual Account to receive funds")
    amount_paise: int = Field(..., gt=0, description="Reimbursement amount in paise")
    description: str = Field(..., min_length=1, description="Purpose and line item details")
    merchant: str | None = Field(None, max_length=100, description="Vendor or merchant name")
    category_code: str | None = Field("5010", description="Expense category code")
    receipt_ref: str | None = Field(None, description="Notion doc URL or reference receipt string")


class Section8ComplianceOut(BaseModel):
    """Schema for Foundation legal governance disclosures under Section 8 of Companies Act, 2013.

    Activated by the GET /api/finance/compliance endpoint: hard-prohibition
    attestations cite their governing rules (docs/legal_governance_rules.md
    §3), the dual-authorization band mirrors live Settings, and the FY label /
    open-commitment count reflect current ledger state.
    """
    foundation_name: str
    licence_number: str
    incorporation_date: str
    corporate_status: str
    rules: list[dict[str, str]]
    # Hard prohibitions — system attestations (True = control in place)
    cash_collection_prohibited: bool = True
    personal_upi_routing_prohibited: bool = True
    local_bank_accounts_prohibited: bool = True
    sponsorship_flows_upstream_first: bool = True
    # Dual authorization band (OKF Rule 35)
    dual_auth_threshold_paise: int
    dual_auth_enabled: bool
    # Financial year (1 April – 31 March)
    fy_start_month: int = 4
    current_fy: str
    # Ledger state
    open_requests_above_threshold: int
    overall_status: Literal["compliant", "warning"]

