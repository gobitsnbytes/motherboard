"""Finance Ledger tests.

Covers: balanced-entry enforcement, reversal-only corrections, period lock,
voucher numbering (sequential + gap-free), cash limits (s.269ST/s.40A(3)),
the FCRA guard, maker-checker (vouchers + donations), trial balance summing
to zero, and the RazorpayX payout stub returning "not configured".
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.finance import compliance, ledger as fin_ledger, reports
from app.finance.models import Donor
from app.finance.payout_provider import RazorpayXNotConfigured, build_payout_provider
from conftest import request_as

TODAY = date(2026, 6, 15)  # FY 2026-27


async def _make_user(db: AsyncSession, name: str, *, super_admin: bool = True) -> User:
    user = User(display_name=name, is_super_admin=super_admin)
    db.add(user)
    await db.commit()
    return user


# ---------------------------------------------------------------------------
# Balanced-entry enforcement
# ---------------------------------------------------------------------------


async def test_unbalanced_entry_rejected(db_session: AsyncSession):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await fin_ledger.post_journal_entry(
            db_session,
            entry_date=TODAY,
            memo="Unbalanced test",
            lines=[
                fin_ledger.JournalLineInput(
                    account_id=accounts["1001"].id, debit_paise=500
                ),
                fin_ledger.JournalLineInput(
                    account_id=accounts["4000"].id, credit_paise=400
                ),
            ],
            source_type="manual",
        )
    assert exc.value.status_code == 400


async def test_single_side_line_rejected(db_session: AsyncSession):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    with pytest.raises(HTTPException):
        await fin_ledger.post_journal_entry(
            db_session,
            entry_date=TODAY,
            memo="Both sides nonzero",
            lines=[
                fin_ledger.JournalLineInput(
                    account_id=accounts["1001"].id, debit_paise=100, credit_paise=100
                ),
                fin_ledger.JournalLineInput(
                    account_id=accounts["4000"].id, credit_paise=100
                ),
            ],
            source_type="manual",
        )


# ---------------------------------------------------------------------------
# Reversal-only corrections
# ---------------------------------------------------------------------------


async def test_reversal_never_mutates_original_entry(db_session: AsyncSession):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    entry = await fin_ledger.post_journal_entry(
        db_session,
        entry_date=TODAY,
        memo="Original posting",
        lines=[
            fin_ledger.JournalLineInput(
                account_id=accounts["1001"].id, debit_paise=1000
            ),
            fin_ledger.JournalLineInput(
                account_id=accounts["4000"].id, credit_paise=1000
            ),
        ],
        source_type="manual",
    )
    await db_session.commit()
    original_memo = entry.memo

    reversal = await fin_ledger.reverse_journal_entry(
        db_session, entry_id=entry.id, posted_by=None
    )
    await db_session.commit()

    # The original row is untouched — same memo, same id, never updated/deleted.
    await db_session.refresh(entry)
    assert entry.memo == original_memo
    assert entry.id != reversal.id
    assert reversal.reverses_entry_id == entry.id
    assert await fin_ledger.is_entry_reversed(db_session, entry.id) is True

    # Trial balance nets back to zero on the affected accounts (reversal cancels it out).
    rows = {r["code"]: r for r in await reports.trial_balance(db_session)}
    assert rows["1001"]["balance_paise"] == 0
    assert rows["4000"]["balance_paise"] == 0


# ---------------------------------------------------------------------------
# Period lock
# ---------------------------------------------------------------------------


async def test_closed_period_blocks_postings(
    db_session: AsyncSession, super_admin: User, client
):
    fy = fin_ledger.fy_label_for(TODAY)
    close_res = await request_as(
        client, super_admin.id, "POST", f"/api/finance/periods/{fy}/close"
    )
    assert close_res.status_code == 200

    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await fin_ledger.post_journal_entry(
            db_session,
            entry_date=TODAY,
            memo="Should not post",
            lines=[
                fin_ledger.JournalLineInput(
                    account_id=accounts["1001"].id, debit_paise=100
                ),
                fin_ledger.JournalLineInput(
                    account_id=accounts["4000"].id, credit_paise=100
                ),
            ],
            source_type="manual",
        )
    assert exc.value.status_code == 409

    reopen_res = await request_as(
        client, super_admin.id, "POST", f"/api/finance/periods/{fy}/reopen"
    )
    assert reopen_res.status_code == 200


# ---------------------------------------------------------------------------
# Voucher numbering (sequential, gap-free, allocated only at approval)
# ---------------------------------------------------------------------------


async def test_voucher_numbers_are_sequential_and_gap_free(
    db_session: AsyncSession, super_admin: User, client
):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    creator = await _make_user(db_session, "Voucher Maker")
    approver = await _make_user(db_session, "Voucher Checker")

    async def make_and_approve():
        create_res = await request_as(
            client,
            creator.id,
            "POST",
            "/api/finance/vouchers",
            json={
                "voucher_type": "payment",
                "voucher_date": TODAY.isoformat(),
                "narration": "Test payment",
                "amount_paise": 5000,
                "debit_account_id": str(accounts["5000"].id),
                "payment_mode": "bank_transfer",
            },
        )
        assert create_res.status_code == 201
        voucher_id = create_res.json()["id"]
        assert (
            create_res.json()["voucher_number"] is None
        )  # not allocated at draft time

        submit_res = await request_as(
            client, creator.id, "POST", f"/api/finance/vouchers/{voucher_id}/submit"
        )
        assert submit_res.status_code == 200

        approve_res = await request_as(
            client,
            approver.id,
            "POST",
            f"/api/finance/vouchers/{voucher_id}/approve",
            json={"note": None},
        )
        assert approve_res.status_code == 200
        return approve_res.json()["voucher_number"]

    # A rejected draft must NOT consume a sequence number.
    reject_create = await request_as(
        client,
        creator.id,
        "POST",
        "/api/finance/vouchers",
        json={
            "voucher_type": "payment",
            "voucher_date": TODAY.isoformat(),
            "narration": "Will be rejected",
            "amount_paise": 1000,
            "debit_account_id": str(accounts["5000"].id),
            "payment_mode": "bank_transfer",
        },
    )
    reject_id = reject_create.json()["id"]
    await request_as(
        client, creator.id, "POST", f"/api/finance/vouchers/{reject_id}/submit"
    )
    reject_res = await request_as(
        client,
        approver.id,
        "POST",
        f"/api/finance/vouchers/{reject_id}/reject",
        json={"note": "no"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["voucher_number"] is None

    first = await make_and_approve()
    second = await make_and_approve()
    fy = fin_ledger.fy_label_for(TODAY)
    assert first == f"PV/{fy}/000001"
    assert second == f"PV/{fy}/000002"


# ---------------------------------------------------------------------------
# Cash limits
# ---------------------------------------------------------------------------


def test_cash_receipt_limit_s269st():
    compliance.check_cash_receipt(199_999 * 100, "cash")  # fine, under threshold
    with pytest.raises(HTTPException) as exc:
        compliance.check_cash_receipt(200_000 * 100, "cash")
    assert exc.value.status_code == 400
    compliance.check_cash_receipt(
        50_000_000, "bank_transfer"
    )  # non-cash mode never blocked


def test_cash_payment_limit_s40a3():
    compliance.check_cash_payment(
        10_000 * 100, "cash"
    )  # fine, at threshold (not exceeding)
    with pytest.raises(HTTPException) as exc:
        compliance.check_cash_payment(10_001 * 100, "cash")
    assert exc.value.status_code == 400


async def test_voucher_creation_rejects_over_limit_cash_payment(
    db_session: AsyncSession, client
):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    creator = await _make_user(db_session, "Cash Spender")

    res = await request_as(
        client,
        creator.id,
        "POST",
        "/api/finance/vouchers",
        json={
            "voucher_type": "payment",
            "voucher_date": TODAY.isoformat(),
            "narration": "Big cash payment",
            "amount_paise": 15_000 * 100,
            "debit_account_id": str(accounts["5000"].id),
            "payment_mode": "cash",
        },
    )
    assert res.status_code == 400
    assert "40A(3)" in res.json()["detail"]


# ---------------------------------------------------------------------------
# FCRA guard
# ---------------------------------------------------------------------------


async def test_fcra_guard_blocks_foreign_donation_without_registration(
    db_session: AsyncSession, client
):
    creator = await _make_user(db_session, "Donation Recorder")
    donor = Donor(
        name="Overseas Friends Inc.",
        donor_type="foreign",
        is_foreign_source=True,
        country="US",
        pan="ABCDE1234F",
    )
    db_session.add(donor)
    await db_session.commit()

    res = await request_as(
        client,
        creator.id,
        "POST",
        "/api/finance/donations",
        json={
            "donor_id": str(donor.id),
            "donation_date": TODAY.isoformat(),
            "amount_paise": 50_000,
            "mode": "bank_transfer",
        },
    )
    assert res.status_code == 403
    assert "FCRA" in res.json()["detail"]

    # Once the FCRA registration number is on file, the same donation succeeds.
    settings_res = await request_as(
        client,
        creator.id,
        "PATCH",
        "/api/finance/settings/org",
        json={"fcra_registration_no": "FCRA/UP/999999"},
    )
    assert settings_res.status_code == 200

    res2 = await request_as(
        client,
        creator.id,
        "POST",
        "/api/finance/donations",
        json={
            "donor_id": str(donor.id),
            "donation_date": TODAY.isoformat(),
            "amount_paise": 50_000,
            "mode": "bank_transfer",
        },
    )
    assert res2.status_code == 201


# ---------------------------------------------------------------------------
# Maker-checker
# ---------------------------------------------------------------------------


async def test_voucher_maker_cannot_approve_own_voucher(
    db_session: AsyncSession, client
):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    creator = await _make_user(db_session, "Solo Maker")

    create_res = await request_as(
        client,
        creator.id,
        "POST",
        "/api/finance/vouchers",
        json={
            "voucher_type": "payment",
            "voucher_date": TODAY.isoformat(),
            "narration": "Self approve attempt",
            "amount_paise": 1000,
            "debit_account_id": str(accounts["5000"].id),
            "payment_mode": "bank_transfer",
        },
    )
    voucher_id = create_res.json()["id"]
    await request_as(
        client, creator.id, "POST", f"/api/finance/vouchers/{voucher_id}/submit"
    )

    approve_res = await request_as(
        client,
        creator.id,
        "POST",
        f"/api/finance/vouchers/{voucher_id}/approve",
        json={"note": None},
    )
    assert approve_res.status_code == 403


async def test_donation_recorder_cannot_confirm_own_donation(
    db_session: AsyncSession, client
):
    creator = await _make_user(db_session, "Solo Recorder")
    donor = Donor(name="Local Donor", donor_type="individual", pan="ABCDE1234F")
    db_session.add(donor)
    await db_session.commit()

    create_res = await request_as(
        client,
        creator.id,
        "POST",
        "/api/finance/donations",
        json={
            "donor_id": str(donor.id),
            "donation_date": TODAY.isoformat(),
            "amount_paise": 50_000,
            "mode": "bank_transfer",
        },
    )
    donation_id = create_res.json()["id"]

    confirm_res = await request_as(
        client, creator.id, "POST", f"/api/finance/donations/{donation_id}/confirm"
    )
    assert confirm_res.status_code == 403


# ---------------------------------------------------------------------------
# Trial balance sums to zero
# ---------------------------------------------------------------------------


async def test_trial_balance_debits_equal_credits(db_session: AsyncSession):
    accounts = await fin_ledger.ensure_system_accounts(db_session)
    await db_session.commit()
    for amount in (10_000, 25_000, 7_500):
        await fin_ledger.post_journal_entry(
            db_session,
            entry_date=TODAY,
            memo="Sample posting",
            lines=[
                fin_ledger.JournalLineInput(
                    account_id=accounts["1001"].id, debit_paise=amount
                ),
                fin_ledger.JournalLineInput(
                    account_id=accounts["4000"].id, credit_paise=amount
                ),
            ],
            source_type="manual",
        )
    await db_session.commit()

    rows = await reports.trial_balance(db_session)
    total_debit = sum(r["debit_total_paise"] for r in rows)
    total_credit = sum(r["credit_total_paise"] for r in rows)
    assert total_debit == total_credit
    assert total_debit == 42_500


# ---------------------------------------------------------------------------
# RazorpayX payout stub
# ---------------------------------------------------------------------------


async def test_razorpayx_provider_not_configured():
    settings = get_settings()
    provider = build_payout_provider(settings)
    assert provider.is_configured is False
    with pytest.raises(RazorpayXNotConfigured):
        await provider.create_payout(
            account_number="1", ifsc="X", amount_paise=1, purpose="p", reference_id="r"
        )
    with pytest.raises(RazorpayXNotConfigured):
        await provider.fetch_balance()
    # Webhook verification fails closed with no secret configured — never raises.
    assert provider.verify_webhook(b"{}", "deadbeef") is False


async def test_razorpayx_router_returns_503(
    db_session: AsyncSession, super_admin: User, client
):
    res = await request_as(
        client, super_admin.id, "POST", "/api/finance/razorpayx/payouts"
    )
    assert res.status_code == 503

    webhook_res = await client.post("/api/finance/razorpayx/webhook", content=b"{}")
    assert webhook_res.status_code == 503
