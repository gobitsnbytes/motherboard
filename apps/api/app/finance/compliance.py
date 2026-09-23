"""Statutory cash-handling and FCRA guards for the Finance Ledger.

These are fixed statutory thresholds, not tunables, so they are constants
rather than Settings fields (ponytail: no config knob for a number the law
sets, not us).
"""

from __future__ import annotations

from fastapi import HTTPException, status

# Income-tax Act, 1961, s.269ST — no person may receive INR 2,00,000 or more
# in cash (in aggregate, from a person, in a day / for a single transaction /
# for transactions relating to one event). We enforce it per-receipt here;
# aggregate-per-day matching is a reporting concern, flagged in the donor
# report rather than blocked at write time.
CASH_RECEIPT_LIMIT_PAISE = 200_000 * 100

# Income-tax Act, 1961, s.40A(3) — a cash payment exceeding INR 10,000 for a
# single expenditure is disallowed as a deduction.
CASH_PAYMENT_LIMIT_PAISE = 10_000 * 100

CASH_MODES = {"cash"}

# Common TDS sections for reference (Income-tax Act, 1961, Chapter XVII-B).
# Rates vary by payee category, cumulative threshold, and Finance Act
# amendments — this table is a UI convenience default, not a determination;
# the rate actually applied is entered per bill and should be confirmed by
# the Foundation's CA.
TDS_SECTIONS: dict[str, dict[str, object]] = {
    "194C": {
        "description": "Payments to contractors/sub-contractors",
        "default_rate_bps": 100,
    },
    "194J": {
        "description": "Fees for professional or technical services",
        "default_rate_bps": 1000,
    },
    "194H": {"description": "Commission or brokerage", "default_rate_bps": 500},
    "194I": {"description": "Rent", "default_rate_bps": 1000},
    "194Q": {"description": "Purchase of goods", "default_rate_bps": 10},
}


def check_cash_receipt(amount_paise: int, mode: str) -> None:
    """Raise 400 when a cash receipt hits the s.269ST threshold."""
    if mode in CASH_MODES and amount_paise >= CASH_RECEIPT_LIMIT_PAISE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cash receipts of INR 2,00,000 or more are prohibited "
                "(Income-tax Act, 1961, s.269ST). Use a bank/UPI/cheque mode."
            ),
        )


def check_cash_payment(amount_paise: int, mode: str) -> None:
    """Raise 400 when a cash payment exceeds the s.40A(3) threshold."""
    if mode in CASH_MODES and amount_paise > CASH_PAYMENT_LIMIT_PAISE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cash payments exceeding INR 10,000 for a single expenditure are "
                "disallowed (Income-tax Act, 1961, s.40A(3)). Use a bank/UPI/cheque mode."
            ),
        )


def check_fcra(*, is_foreign_source: bool, fcra_registration_no: str | None) -> None:
    """Raise 403 when a foreign-source contribution arrives without FCRA registration.

    Foreign Contribution (Regulation) Act, 2010, s.6 — no association may
    accept "foreign contribution" without FCRA registration (or prior
    permission). We fail closed: unless a registration number is on file in
    FinOrgSettings, foreign-source donations are blocked outright.
    """
    if is_foreign_source and not fcra_registration_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Foreign-source contributions are blocked: no FCRA registration is on "
                "file (Foreign Contribution (Regulation) Act, 2010, s.6). Record the "
                "Foundation's FCRA registration number under Finance Settings first, or "
                "route this contribution through a registered channel."
            ),
        )
