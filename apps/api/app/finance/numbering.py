"""Sequential, gap-free document numbering (vouchers, donation receipts).

Numbers are allocated from a per-(financial year, series) counter row, taken
under a row lock so concurrent approvals cannot allocate the same number.
Callers must allocate the number in the same DB transaction as the state
change that makes it permanent (approval/confirmation), never at draft
creation — otherwise a rejected draft would burn a number and leave a gap.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance.models import VoucherCounter

SERIES_PREFIX = {
    "payment": "PV",
    "receipt": "RV",
    "journal": "JV",
    "donation": "DR",
}


async def next_document_number(db: AsyncSession, fy_label: str, series: str) -> str:
    """Allocate and return the next formatted number, e.g. ``PV/2026-27/000001``.

    Must be called within an open transaction that the caller commits; the
    row lock (``with_for_update``) held until that commit is what keeps
    allocation gap-free under concurrency (best-effort on SQLite, which has
    no real row locking — fine for tests/dev, Postgres enforces it for real).
    """
    prefix = SERIES_PREFIX.get(series, series.upper())
    result = await db.execute(
        select(VoucherCounter)
        .where(VoucherCounter.fy_label == fy_label, VoucherCounter.series == series)
        .with_for_update()
    )
    counter = result.scalar_one_or_none()
    if counter is None:
        counter = VoucherCounter(fy_label=fy_label, series=series, next_number=1)
        db.add(counter)
        await db.flush()
    number = counter.next_number
    counter.next_number = number + 1
    return f"{prefix}/{fy_label}/{number:06d}"
