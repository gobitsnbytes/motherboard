"""Maps the existing paper VirtualAccount/MoneyRequest/card-charge flows
(app.routers.finance) onto balanced journal entries.

Called from within the existing endpoints, in the same DB transaction, right
before their ``db.commit()`` — so the paper ledger (VirtualAccount.balance_paise,
VirtualTransaction rows) and the double-entry journal are always posted
together. Endpoint request/response shapes are unchanged; this is a
side-effect only, which is what keeps the migration and these endpoints
backward compatible.

If the target financial year is closed, journal mapping raises 409 same as
any other posting — a closed period blocks new money movement everywhere,
not just in the ledger UI.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VirtualAccount, VirtualCard
from app.finance.ledger import (
    JournalLineInput,
    get_or_create_account,
    get_or_create_fund_account,
    post_journal_entry,
)
from app.finance.models import JournalEntry


async def post_for_money_request_approval(
    db: AsyncSession,
    *,
    from_account: VirtualAccount | None,
    to_account: VirtualAccount,
    amount_paise: int,
    description: str,
    request_id: uuid.UUID,
    approved_by: uuid.UUID,
) -> JournalEntry:
    """Debit the source fund (or the Unallocated Treasury Fund for a pool
    draw), credit the destination fund."""
    to_fund = await get_or_create_fund_account(db, to_account)
    if from_account is not None:
        from_fund = await get_or_create_fund_account(db, from_account)
        debit_account_id = from_fund.id
    else:
        treasury = await get_or_create_account(db, "3000")
        debit_account_id = treasury.id

    lines = [
        JournalLineInput(
            account_id=debit_account_id,
            debit_paise=amount_paise,
            description=description,
        ),
        JournalLineInput(
            account_id=to_fund.id, credit_paise=amount_paise, description=description
        ),
    ]
    return await post_journal_entry(
        db,
        entry_date=datetime.now(timezone.utc).date(),
        memo=f"Money request approved: {description}",
        lines=lines,
        source_type="money_request",
        source_id=request_id,
        posted_by=approved_by,
    )


async def post_for_card_charge(
    db: AsyncSession,
    *,
    card: VirtualCard,
    account: VirtualAccount,
    amount_paise: int,
    merchant: str,
    description: str,
    transaction_id: uuid.UUID,
    charged_by: uuid.UUID,
) -> JournalEntry:
    """A card charge is real expenditure: debit the expense account, credit
    the card's parent fund."""
    fund = await get_or_create_fund_account(db, account)
    expense = await get_or_create_account(db, "5900")
    memo = f"Card charge: {merchant} — {description}"
    lines = [
        JournalLineInput(
            account_id=expense.id, debit_paise=amount_paise, description=memo
        ),
        JournalLineInput(
            account_id=fund.id, credit_paise=amount_paise, description=memo
        ),
    ]
    return await post_journal_entry(
        db,
        entry_date=datetime.now(timezone.utc).date(),
        memo=memo,
        lines=lines,
        source_type="card_charge",
        source_id=transaction_id,
        posted_by=charged_by,
    )
