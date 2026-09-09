"""
RazorpayX ledger adapter seam.

The Foundation ledger is currently a virtual paper ledger (pure DB, zero
network). This module defines the seam where a real RazorpayX banking
provider will plug in later, without the finance router knowing which one
is active:

    adapter = build_adapter(settings, db)
    result  = await adapter.create_account(LedgerAccountRequest(...))
    result  = await adapter.issue_card(CardIssueRequest(...))
    txns    = await adapter.list_transactions(TransactionQuery(...))

Adapters are provider-side provisioning only: they mint identifiers and
read provider transactions. The router keeps ownership of local ORM rows so
response shapes never change when the provider flips.

Selection logic (build_adapter):
    * razorpayx_key_id + razorpayx_secret both configured
        -> RazorpayXLiveAdapter (raises NotImplementedError until the real
           API wiring lands — loud failure instead of silently writing paper
           rows in a deployment that expects real banking).
    * otherwise (default, disabled)
        -> PaperLedgerAdapter — pure local DB, no network calls.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import VirtualAccount, VirtualTransaction


# ---------------------------------------------------------------------------
# Typed request/result contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerAccountRequest:
    """Provisioning request for a new ledger account."""
    name: str
    owner_id: uuid.UUID
    description: str | None = None


@dataclass(frozen=True)
class LedgerAccountResult:
    """Provider-issued account identifiers to persist locally."""
    account_number: str
    ifsc: str


@dataclass(frozen=True)
class CardIssueRequest:
    """Provisioning request for a new card on an existing account."""
    account_id: uuid.UUID
    holder_id: uuid.UUID
    card_name: str
    card_type: str  # 'virtual' | 'debit'
    expires_month: int
    expires_year: int
    daily_limit_paise: int | None = None
    monthly_limit_paise: int | None = None


@dataclass(frozen=True)
class CardIssueResult:
    """Provider-issued card identifiers to persist locally."""
    last_four: str
    card_type: str


@dataclass(frozen=True)
class TransactionQuery:
    """Filter parameters for listing provider-side transactions."""
    account_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 100


@dataclass(frozen=True)
class TransactionRecord:
    """A single provider-side transaction entry."""
    reference: str
    amount_paise: int
    narration: str
    created_at: datetime
    source_account_id: uuid.UUID | None = None
    destination_account_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------

class RazorpayXAdapter(Protocol):
    """Common surface for paper and live ledger providers."""

    async def create_account(self, request: LedgerAccountRequest) -> LedgerAccountResult: ...

    async def issue_card(self, request: CardIssueRequest) -> CardIssueResult: ...

    async def list_transactions(self, query: TransactionQuery) -> Sequence[TransactionRecord]: ...


# ---------------------------------------------------------------------------
# Paper ledger implementation (default)
# ---------------------------------------------------------------------------

class PaperLedgerAdapter:
    """Virtual paper-ledger provider.

    Pure local DB — zero network. Mints deterministic VIRT-* account numbers
    (uniqueness-checked against virtual_accounts) and random card suffixes.
    Does NOT insert rows; the router persists local ORM records using the
    returned identifiers, keeping transaction control with the caller.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _unique_account_number(self) -> str:
        for _ in range(10):
            candidate = f"VIRT-{uuid.uuid4().hex[:10].upper()}"
            exists = await self._db.execute(
                sa.select(VirtualAccount.account_number).where(
                    VirtualAccount.account_number == candidate
                )
            )
            if exists.scalar_one_or_none() is None:
                return candidate
        raise RuntimeError("Could not allocate a unique virtual account number.")

    async def create_account(self, request: LedgerAccountRequest) -> LedgerAccountResult:
        return LedgerAccountResult(
            account_number=await self._unique_account_number(),
            ifsc="GOBN0001001",
        )

    async def issue_card(self, request: CardIssueRequest) -> CardIssueResult:
        return CardIssueResult(
            last_four=uuid.uuid4().hex[:4].upper(),
            card_type=request.card_type,
        )

    async def list_transactions(self, query: TransactionQuery) -> Sequence[TransactionRecord]:
        stmt = (
            sa.select(VirtualTransaction)
            .order_by(VirtualTransaction.created_at.desc())
            .limit(query.limit)
        )
        if query.date_from is not None:
            stmt = stmt.where(VirtualTransaction.created_at >= query.date_from)
        if query.date_to is not None:
            stmt = stmt.where(VirtualTransaction.created_at < query.date_to)
        if query.account_id is not None:
            stmt = stmt.where(
                (VirtualTransaction.source_account_id == query.account_id)
                | (VirtualTransaction.destination_account_id == query.account_id)
            )
        result = await self._db.execute(stmt)
        return [
            TransactionRecord(
                reference=f"VT-{txn.id}",
                amount_paise=txn.amount_paise,
                narration=txn.description,
                created_at=txn.created_at,
                source_account_id=txn.source_account_id,
                destination_account_id=txn.destination_account_id,
            )
            for txn in result.scalars().all()
        ]


# ---------------------------------------------------------------------------
# Live RazorpayX stub
# ---------------------------------------------------------------------------

class RazorpayXLiveAdapter:
    """Placeholder for the real RazorpayX current-account / card APIs.

    Constructed only when both RAZORPAYX_KEY_ID and RAZORPAYX_SECRET are set.
    Every method fails loudly with NotImplementedError until the live wiring
    is implemented, so a production deployment never mistakes paper rows for
    real bank activity.
    """

    def __init__(self, key_id: str, secret: str) -> None:
        self._key_id = key_id
        self._secret = secret

    def _not_wired(self) -> NotImplementedError:
        return NotImplementedError(
            "RazorpayX live banking is not implemented yet. The adapter seam "
            "(app.services.razorpayx_adapter) is configured with live keys, but "
            "no API wiring exists. Unset RAZORPAYX_KEY_ID/RAZORPAYX_SECRET to "
            "run the virtual paper ledger instead."
        )

    async def create_account(self, request: LedgerAccountRequest) -> LedgerAccountResult:
        raise self._not_wired()

    async def issue_card(self, request: CardIssueRequest) -> CardIssueResult:
        raise self._not_wired()

    async def list_transactions(self, query: TransactionQuery) -> Sequence[TransactionRecord]:
        raise self._not_wired()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_adapter(settings: Settings, db: AsyncSession) -> RazorpayXAdapter:
    """Choose the ledger adapter for this deployment.

    Default (no RazorpayX credentials configured): PaperLedgerAdapter.
    With credentials set: RazorpayXLiveAdapter stub (raises until wired).
    """
    if settings.razorpayx_key_id and settings.razorpayx_secret:
        return RazorpayXLiveAdapter(
            key_id=settings.razorpayx_key_id, secret=settings.razorpayx_secret
        )
    return PaperLedgerAdapter(db)
