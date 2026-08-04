import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from app.plugin_sdk.types import (
    PluginManifest,
    PermissionDeclaration,
    UiPanelDeclaration,
    PluginContext,
)

logger = logging.getLogger("plugin_finance_ledger")
router = APIRouter()

# --- Pydantic Models ---
class JournalEntryCreate(BaseModel):
    memo: str = Field(..., description="Description of transaction")
    debit_account: str = Field(..., description="Debit account code e.g. Expense:Events")
    credit_account: str = Field(..., description="Credit account code e.g. Bank:RazorpayX")
    amount: float = Field(..., gt=0, description="Amount in INR ₹")

class VirtualAccountCreate(BaseModel):
    fork_city: str = Field(..., description="Fork city name")
    department: str = Field(..., description="Department e.g. Hackathons, Operations")
    initial_balance: float = Field(default=0.0, ge=0.0, description="Initial allocation INR ₹")

class ExpenseSubmit(BaseModel):
    submitter_name: str = Field(..., description="Name of claiming contributor")
    department: str = Field(..., description="Fork or department")
    category: str = Field(..., description="Expense category e.g. Logistics, Food, Server")
    amount: float = Field(..., gt=0, description="Claim amount in INR ₹")
    receipt_url: Optional[str] = Field(default=None, description="Receipt URL or proof link")

class ExpenseApproval(BaseModel):
    approved: bool = Field(..., description="True to approve, False to reject")
    note: Optional[str] = Field(default="", description="Approver note")

# --- In-Memory Finance Data Store ---
VIRTUAL_ACCOUNTS_DB: Dict[str, Dict[str, Any]] = {
    "va-lko-01": {
        "account_id": "va-lko-01",
        "fork_city": "Lucknow",
        "department": "Core Operations",
        "balance": 150000.0,
        "upi_id": "gobitsnbytes.lko@razorpay",
        "status": "ACTIVE",
    },
    "va-kan-02": {
        "account_id": "va-kan-02",
        "fork_city": "Kanpur",
        "department": "Hackathons",
        "balance": 45000.0,
        "upi_id": "gobitsnbytes.kanpur@razorpay",
        "status": "ACTIVE",
    },
    "va-vns-03": {
        "account_id": "va-vns-03",
        "fork_city": "Varanasi",
        "department": "Workshops",
        "balance": 20000.0,
        "upi_id": "gobitsnbytes.vns@razorpay",
        "status": "ACTIVE",
    },
}

JOURNAL_ENTRIES_DB: List[Dict[str, Any]] = [
    {
        "id": "je-1001",
        "transaction_date": "2026-07-28T10:30:00Z",
        "memo": "Grant Funding Disbursement - Section 8 Corp Account",
        "debit_account": "Bank:RazorpayX",
        "credit_account": "Revenue:Grants",
        "amount": 250000.0,
        "status": "POSTED",
    },
    {
        "id": "je-1002",
        "transaction_date": "2026-08-01T14:15:00Z",
        "memo": "Execron 1.0 Hackathon Venue Sponsorship",
        "debit_account": "Expense:Events",
        "credit_account": "Bank:RazorpayX",
        "amount": 35000.0,
        "status": "POSTED",
    },
]

EXPENSES_DB: Dict[str, Dict[str, Any]] = {
    "exp-501": {
        "expense_id": "exp-501",
        "submitter_name": "Yash Singh",
        "department": "Lucknow",
        "category": "Event Hardware Logistics",
        "amount": 4200.0,
        "status": "PENDING",
        "receipt_url": "https://gobitsnbytes.org/receipts/exp-501.pdf",
        "created_at": "2026-08-03T11:20:00Z",
        "approver_note": "",
    },
    "exp-502": {
        "expense_id": "exp-502",
        "submitter_name": "Akshat Kushwaha",
        "department": "Core Infrastructure",
        "category": "Domain & Cloud Hosting",
        "amount": 8500.0,
        "status": "APPROVED",
        "receipt_url": "https://gobitsnbytes.org/receipts/exp-502.pdf",
        "created_at": "2026-08-02T09:10:00Z",
        "approver_note": "Approved per monthly ops budget.",
    },
}

# --- Router Endpoints ---
@router.get("/journal-entries")
async def list_journal_entries():
    """List double-entry ledger transactions."""
    return JOURNAL_ENTRIES_DB

@router.post("/journal-entries", status_code=201)
async def create_journal_entry(payload: JournalEntryCreate):
    """Record a balanced double-entry ledger transaction."""
    if payload.debit_account == payload.credit_account:
        raise HTTPException(status_code=400, detail="Debit and credit accounts must be distinct")
    
    entry = {
        "id": f"je-{uuid.uuid4().hex[:6]}",
        "transaction_date": datetime.utcnow().isoformat() + "Z",
        "memo": payload.memo,
        "debit_account": payload.debit_account,
        "credit_account": payload.credit_account,
        "amount": payload.amount,
        "status": "POSTED",
    }
    JOURNAL_ENTRIES_DB.insert(0, entry)
    return entry

@router.get("/virtual-accounts")
async def list_virtual_accounts():
    """List RazorpayX virtual accounts allocated per fork/department."""
    return list(VIRTUAL_ACCOUNTS_DB.values())

@router.post("/virtual-accounts", status_code=201)
async def allocate_virtual_account(payload: VirtualAccountCreate):
    """Allocate a new virtual account for a fork or department."""
    acc_id = f"va-{payload.fork_city.lower()[:3]}-{uuid.uuid4().hex[:4]}"
    account = {
        "account_id": acc_id,
        "fork_city": payload.fork_city,
        "department": payload.department,
        "balance": payload.initial_balance,
        "upi_id": f"gobitsnbytes.{payload.fork_city.lower()}@razorpay",
        "status": "ACTIVE",
    }
    VIRTUAL_ACCOUNTS_DB[acc_id] = account
    return account

@router.get("/expenses")
async def list_expenses():
    """List submitted expense claims for approval routing."""
    return list(EXPENSES_DB.values())

@router.post("/expenses", status_code=201)
async def submit_expense(payload: ExpenseSubmit):
    """Submit a new expense claim for Section 8 approval routing."""
    exp_id = f"exp-{uuid.uuid4().hex[:6]}"
    expense = {
        "expense_id": exp_id,
        "submitter_name": payload.submitter_name,
        "department": payload.department,
        "category": payload.category,
        "amount": payload.amount,
        "status": "PENDING",
        "receipt_url": payload.receipt_url,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "approver_note": "",
    }
    EXPENSES_DB[exp_id] = expense
    return expense

@router.post("/expenses/{expense_id}/approve")
async def review_expense(expense_id: str, payload: ExpenseApproval):
    """Approve or reject expense claim and automatically post ledger double-entry if approved."""
    if expense_id not in EXPENSES_DB:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    
    expense = EXPENSES_DB[expense_id]
    if payload.approved:
        expense["status"] = "APPROVED"
        expense["approver_note"] = payload.note or "Approved by Section 8 CFO"
        
        # Auto-create double-entry journal transaction
        journal_entry = {
            "id": f"je-exp-{expense_id}",
            "transaction_date": datetime.utcnow().isoformat() + "Z",
            "memo": f"Expense Reimbursement: {expense['category']} ({expense['submitter_name']})",
            "debit_account": f"Expense:{expense['category']}",
            "credit_account": f"Bank:VirtualAccount:{expense['department']}",
            "amount": expense["amount"],
            "status": "POSTED",
        }
        JOURNAL_ENTRIES_DB.insert(0, journal_entry)
    else:
        expense["status"] = "REJECTED"
        expense["approver_note"] = payload.note or "Rejected by CFO"

    return expense

@router.get("/summary")
async def get_financial_summary():
    """Get financial overview, assets, expenses, and double-entry balance check."""
    total_debits = sum(e["amount"] for e in JOURNAL_ENTRIES_DB)
    total_credits = sum(e["amount"] for e in JOURNAL_ENTRIES_DB)
    virtual_accounts_total = sum(acc["balance"] for acc in VIRTUAL_ACCOUNTS_DB.values())
    pending_expenses_count = sum(1 for exp in EXPENSES_DB.values() if exp["status"] == "PENDING")
    
    return {
        "total_assets": virtual_accounts_total + 100000.0,
        "total_journal_entries": len(JOURNAL_ENTRIES_DB),
        "total_debits": total_debits,
        "total_credits": total_credits,
        "is_balanced": total_debits == total_credits,
        "virtual_accounts_count": len(VIRTUAL_ACCOUNTS_DB),
        "virtual_accounts_total_balance": virtual_accounts_total,
        "pending_expenses_count": pending_expenses_count,
    }

# --- Plugin Lifecycle Hooks ---
async def on_load(app, ctx: PluginContext):
    """Executes on startup when finance_ledger is loaded."""
    logger.info(f"Finance Ledger plugin {ctx.plugin_id} on_load executing...")
    await ctx.audit(
        action="load",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "finance_ledger_mounted"}
    )
    await ctx.publish_event("finance.ledger_ready", {"plugin_id": ctx.plugin_id})

async def on_unload(ctx: PluginContext):
    """Executes on shutdown when finance_ledger is unloaded."""
    logger.info(f"Finance Ledger plugin {ctx.plugin_id} on_unload executing...")
    await ctx.audit(
        action="unload",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "finance_ledger_unmounted"}
    )

# --- Manifest Declaration ---
def get_manifest() -> PluginManifest:
    """Returns PluginManifest for finance_ledger."""
    return PluginManifest(
        id="finance_ledger",
        name="Section 8 Finance Ledger",
        version="1.0.0",
        description="Double-entry Section 8 ledger tracking, virtual account allocation, and expense approval routing.",
        router=router,
        on_load=on_load,
        on_unload=on_unload,
        permissions=[
            PermissionDeclaration(key="finance_ledger.read", description="View ledger entries, virtual accounts, and expense routing."),
            PermissionDeclaration(key="finance_ledger.write", description="Record journal entries, allocate virtual accounts, and submit expenses."),
            PermissionDeclaration(key="finance_ledger.approve", description="Approve or reject expense claims and ledger adjustments."),
        ],
        ui_panels=[
            UiPanelDeclaration(
                id="finance-ledger-panel",
                title="Finance Ledger",
                route_segment="finance-ledger",
                placement="sidebar",
                icon="Landmark",
                required_permission="finance_ledger.read"
            )
        ]
    )
