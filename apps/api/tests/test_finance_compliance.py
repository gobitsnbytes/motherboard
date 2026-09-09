"""
Finance governance compliance tests.

Covers: self-approval prohibition, OKF Rule 35 dual authorization band,
Section 8 compliance disclosure endpoint, audit trail writes, FY CSV export,
and the RazorpayX adapter seam.
"""

import csv
import io
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.db.models import (
    AuditLog,
    MoneyRequest,
    User,
    VirtualAccount,
    VirtualTransaction,
)
from app.main import app
from app.services.razorpayx_adapter import (
    CardIssueRequest,
    LedgerAccountRequest,
    PaperLedgerAdapter,
    RazorpayXLiveAdapter,
    TransactionQuery,
    build_adapter,
)
from conftest import request_as

DEFAULT_THRESHOLD_PAISE = 10_000_000  # ₹1,00,000


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_user(db: AsyncSession, name: str, *, super_admin: bool = True) -> User:
    user = User(display_name=name, is_super_admin=super_admin)
    db.add(user)
    await db.commit()
    return user


async def _make_account(
    db: AsyncSession, owner: User, balance_paise: int = 0
) -> VirtualAccount:
    account = VirtualAccount(
        owner_id=owner.id,
        name=f"Account {uuid.uuid4().hex[:6]}",
        account_number=f"VIRT-{uuid.uuid4().hex[:10].upper()}",
        balance_paise=balance_paise,
    )
    db.add(account)
    await db.commit()
    return account


async def _create_request(client, user: User, to_account_id, amount_paise, **overrides):
    payload = {
        "to_account_id": str(to_account_id),
        "amount_paise": amount_paise,
        "description": "Compliance test request",
        **overrides,
    }
    return await request_as(
        client, user.id, "POST", "/api/finance/requests", json=payload
    )


async def _review(client, user: User, request_id, action: str):
    return await request_as(
        client,
        user.id,
        "POST",
        f"/api/finance/requests/{request_id}/{action}",
        json={"note": None},
    )


async def _audit_rows(db: AsyncSession, action: str, target_id: str | None = None):
    stmt = select(AuditLog).where(AuditLog.action == action)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())


def _current_fy() -> str:
    today = datetime.now(timezone.utc).date()
    start_year = today.year if today.month >= 4 else today.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


# ---------------------------------------------------------------------------
# Self-approval prohibition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_approval_forbidden_on_approve_and_reject(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        requester = await _make_user(db_session, "Self Approver")
        account = await _make_account(db_session, super_admin)

        create_res = await _create_request(ac, requester, account.id, 50_000)
        assert create_res.status_code == 201
        request_id = create_res.json()["id"]

        approve_res = await _review(ac, requester, request_id, "approve")
        assert approve_res.status_code == 403

        reject_res = await _review(ac, requester, request_id, "reject")
        assert reject_res.status_code == 403

    # Request untouched and still pending
    req = await db_session.get(MoneyRequest, uuid.UUID(request_id))
    await db_session.refresh(req)
    assert req.status == "pending"
    assert req.reviewed_by is None


# ---------------------------------------------------------------------------
# Dual authorization band (OKF Rule 35)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_small_request_single_approval_moves_funds(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        requester = await _make_user(db_session, "Small Req")
        approver = await _make_user(db_session, "Small Approver")
        account = await _make_account(db_session, requester)

        create_res = await _create_request(
            ac, requester, account.id, DEFAULT_THRESHOLD_PAISE - 1
        )
        assert create_res.status_code == 201
        body = create_res.json()
        assert body["dual_approval_required"] is False

        approve_res = await _review(ac, approver, body["id"], "approve")
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "approved"

    await db_session.refresh(account)
    assert account.balance_paise == DEFAULT_THRESHOLD_PAISE - 1


@pytest.mark.asyncio
async def test_large_request_requires_two_distinct_approvers(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        requester = await _make_user(db_session, "Big Req")
        approver_a = await _make_user(db_session, "Approver A")
        approver_b = await _make_user(db_session, "Approver B")
        account = await _make_account(db_session, requester)

        create_res = await _create_request(
            ac, requester, account.id, DEFAULT_THRESHOLD_PAISE
        )
        body = create_res.json()
        request_id = body["id"]
        assert body["dual_approval_required"] is True
        assert body["approvals_count"] == 0

        # First distinct approver — recorded, funds NOT moved yet
        first = await _review(ac, approver_a, request_id, "approve")
        assert first.status_code == 200
        assert first.json()["status"] == "pending"
        assert first.json()["dual_approval_required"] is True
        assert first.json()["approvals_count"] == 1
        assert first.json()["required_approvals"] == 2

        # Duplicate signature from the same approver does not advance progress
        dup = await _review(ac, approver_a, request_id, "approve")
        assert dup.status_code == 200
        assert dup.json()["status"] == "pending"
        assert dup.json()["approvals_count"] == 1

        # Progress visible on GET endpoints
        got = await request_as(ac, super_admin.id, "GET", f"/api/finance/requests/{request_id}")
        assert got.status_code == 200
        assert got.json()["approvals_count"] == 1

        # Second distinct approver completes the commitment
        second = await _review(ac, approver_b, request_id, "approve")
        assert second.status_code == 200
        final = second.json()
        assert final["status"] == "approved"
        assert final["approvals_count"] == 2
        assert final["dual_approval_required"] is True

    # Balances moved exactly once
    await db_session.refresh(account)
    assert account.balance_paise == DEFAULT_THRESHOLD_PAISE

    txns = await db_session.execute(
        select(VirtualTransaction).where(VirtualTransaction.reference_type == "money_request")
    )
    assert len(list(txns.scalars().all())) == 1

    signatures = await _audit_rows(
        db_session, "finance.request.approval_recorded", request_id
    )
    assert len(signatures) == 2
    assert {str(s.actor_id) for s in signatures} == {
        str(approver_a.id),
        str(approver_b.id),
    }


@pytest.mark.asyncio
async def test_dual_approval_disabled_moves_funds_immediately(
    db_session: AsyncSession, super_admin: User, monkeypatch
):
    monkeypatch.setenv("FINANCE_DUAL_APPROVAL_ENABLED", "false")
    get_settings.cache_clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            requester = await _make_user(db_session, "Disabled Band Req")
            approver = await _make_user(db_session, "Sole Approver")
            account = await _make_account(db_session, requester)

            create_res = await _create_request(
                ac, requester, account.id, DEFAULT_THRESHOLD_PAISE * 2
            )
            request_id = create_res.json()["id"]

            approve_res = await _review(ac, approver, request_id, "approve")
            assert approve_res.status_code == 200
            assert approve_res.json()["status"] == "approved"

        await db_session.refresh(account)
        assert account.balance_paise == DEFAULT_THRESHOLD_PAISE * 2
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Section 8 compliance endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_endpoint_shape(db_session: AsyncSession, super_admin: User):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await request_as(ac, super_admin.id, "GET", "/api/finance/compliance")
        assert res.status_code == 200
        data = res.json()

        assert data["foundation_name"] == "GOBITSNBYTES FOUNDATION"
        assert "186266" in data["licence_number"]
        assert data["incorporation_date"] == "2026-06-02"
        assert "Section 8" in data["corporate_status"]

        assert data["cash_collection_prohibited"] is True
        assert data["personal_upi_routing_prohibited"] is True
        assert data["local_bank_accounts_prohibited"] is True
        assert data["sponsorship_flows_upstream_first"] is True

        settings = get_settings()
        assert data["dual_auth_threshold_paise"] == settings.finance_dual_approval_threshold_paise
        assert data["dual_auth_enabled"] == settings.finance_dual_approval_enabled

        assert data["fy_start_month"] == 4
        assert data["current_fy"] == _current_fy()
        assert data["overall_status"] in {"compliant", "warning"}

        citations = {r["rule"]: r["citation"] for r in data["rules"]}
        assert all("IOM v2.0" in c for c in citations.values())


@pytest.mark.asyncio
async def test_compliance_counts_open_requests_above_threshold(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        before = await request_as(ac, super_admin.id, "GET", "/api/finance/compliance")
        baseline = before.json()["open_requests_above_threshold"]

        requester = await _make_user(db_session, "Pending Big Req")
        account = await _make_account(db_session, requester)
        create_res = await _create_request(
            ac, requester, account.id, DEFAULT_THRESHOLD_PAISE + 1
        )
        assert create_res.status_code == 201

        after = await request_as(ac, super_admin.id, "GET", "/api/finance/compliance")
        data = after.json()
        assert data["open_requests_above_threshold"] == baseline + 1
        assert data["overall_status"] == "warning"


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_trail_written_for_request_lifecycle_and_card_charge(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        requester = await _make_user(db_session, "Audited Req")
        reviewer = await _make_user(db_session, "Audited Reviewer")
        account = await _make_account(db_session, requester, balance_paise=10_000)

        create_res = await _create_request(ac, requester, account.id, 25_00)
        request_id = create_res.json()["id"]
        created_rows = await _audit_rows(
            db_session, "finance.request.created", request_id
        )
        assert len(created_rows) == 1
        assert created_rows[0].target_type == "money_request"

        reject_res = await _review(ac, reviewer, request_id, "reject")
        assert reject_res.status_code == 200
        rejected_rows = await _audit_rows(
            db_session, "finance.request.rejected", request_id
        )
        assert len(rejected_rows) == 1

        # Approved path + card charge audit
        create_res2 = await _create_request(ac, requester, account.id, 10_00)
        request_id2 = create_res2.json()["id"]
        approve_res = await _review(ac, reviewer, request_id2, "approve")
        assert approve_res.status_code == 200
        approved_rows = await _audit_rows(
            db_session, "finance.request.approved", request_id2
        )
        assert len(approved_rows) == 1

        card_payload = {
            "account_id": str(account.id),
            "holder_id": str(requester.id),
            "card_name": "Audit Card",
            "card_type": "virtual",
            "expires_month": 12,
            "expires_year": 2030,
        }
        card_res = await request_as(
            ac, super_admin.id, "POST", "/api/finance/cards", json=card_payload
        )
        assert card_res.status_code == 201
        card_id = card_res.json()["id"]

        charge_res = await request_as(
            ac,
            super_admin.id,
            "POST",
            f"/api/finance/cards/{card_id}/simulate-charge",
            json={
                "amount_paise": 1_00,
                "merchant": "Test Merchant",
                "description": "Audit trail charge",
            },
        )
        assert charge_res.status_code == 200
        charged_rows = await _audit_rows(db_session, "finance.card.charged", card_id)
        assert len(charged_rows) == 1
        assert charged_rows[0].target_type == "virtual_card"
        assert charged_rows[0].metadata_json["merchant"] == "Test Merchant"


# ---------------------------------------------------------------------------
# FY export (streaming CSV)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fy_export_streams_csv(db_session: AsyncSession, super_admin: User):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        requester = await _make_user(db_session, "Export Req")
        approver = await _make_user(db_session, "Export Approver")
        account = await _make_account(db_session, requester)

        # Pool draw -> inflow row
        create_res = await _create_request(ac, requester, account.id, 50_000)
        request_id = create_res.json()["id"]
        approve_res = await _review(ac, approver, request_id, "approve")
        assert approve_res.status_code == 200

        # Card charge -> outflow row
        card_payload = {
            "account_id": str(account.id),
            "holder_id": str(requester.id),
            "card_name": "Export Card",
            "card_type": "virtual",
            "expires_month": 6,
            "expires_year": 2031,
        }
        card_res = await request_as(
            ac, super_admin.id, "POST", "/api/finance/cards", json=card_payload
        )
        card_id = card_res.json()["id"]
        charge_res = await request_as(
            ac,
            super_admin.id,
            "POST",
            f"/api/finance/cards/{card_id}/simulate-charge",
            json={
                "amount_paise": 2_000,
                "merchant": "CSV Merchant",
                "description": "FY export charge",
            },
        )
        assert charge_res.status_code == 200

        fy = _current_fy()
        export_res = await request_as(
            ac, super_admin.id, "GET", f"/api/finance/reports/fy?fy={fy}"
        )
        assert export_res.status_code == 200
        assert export_res.headers["content-type"].startswith("text/csv")

        rows = list(csv.reader(io.StringIO(export_res.text)))
        assert rows[0] == [
            "date",
            "txn_type",
            "account",
            "counterparty",
            "narration",
            "amount_paise",
            "direction",
        ]
        data_rows = [r for r in rows[1:] if r]
        assert len(data_rows) >= 2

        draw_row = next(r for r in data_rows if r[1] == "money_request")
        assert draw_row[5] == "50000"
        assert draw_row[6] == "inflow"

        charge_row = next(r for r in data_rows if r[1] == "card_charge")
        assert charge_row[5] == "2000"
        assert charge_row[6] == "outflow"


@pytest.mark.asyncio
async def test_fy_export_validates_format_and_span(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for bad in ["2026", "2026/27", "abcd-ef", "2026-28", "2026-270"]:
            res = await request_as(
                ac, super_admin.id, "GET", f"/api/finance/reports/fy?fy={bad}"
            )
            assert res.status_code == 400, f"{bad} should be rejected"


@pytest.mark.asyncio
async def test_fy_export_requires_finance_admin(db_session: AsyncSession):
    plain = await _make_user(db_session, "No Finance Admin", super_admin=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await request_as(
            ac, plain.id, "GET", "/api/finance/reports/fy?fy=2026-27"
        )
        assert res.status_code == 403


# ---------------------------------------------------------------------------
# RazorpayX adapter seam
# ---------------------------------------------------------------------------


class _FakeSettings:
    razorpayx_key_id = None
    razorpayx_secret = None


class _FakeSettingsWithKeys(_FakeSettings):
    razorpayx_key_id = "rzp_test_key"
    razorpayx_secret = "rzp_test_secret"


@pytest.mark.asyncio
async def test_build_adapter_defaults_to_paper(db_session: AsyncSession):
    adapter = build_adapter(_FakeSettings(), db_session)
    assert isinstance(adapter, PaperLedgerAdapter)

    keyed = build_adapter(_FakeSettingsWithKeys(), db_session)
    assert isinstance(keyed, RazorpayXLiveAdapter)


@pytest.mark.asyncio
async def test_live_adapter_raises_not_implemented():
    adapter = RazorpayXLiveAdapter(key_id="k", secret="s")
    with pytest.raises(NotImplementedError, match="RazorpayX"):
        await adapter.create_account(
            LedgerAccountRequest(name="X", owner_id=uuid.uuid4())
        )
    with pytest.raises(NotImplementedError, match="RazorpayX"):
        await adapter.issue_card(
            CardIssueRequest(
                account_id=uuid.uuid4(),
                holder_id=uuid.uuid4(),
                card_name="X",
                card_type="virtual",
                expires_month=1,
                expires_year=2030,
            )
        )
    with pytest.raises(NotImplementedError, match="RazorpayX"):
        await adapter.list_transactions(TransactionQuery())


@pytest.mark.asyncio
async def test_paper_adapter_creates_unique_virt_numbers(db_session: AsyncSession):
    adapter = PaperLedgerAdapter(db_session)
    result = await adapter.create_account(
        LedgerAccountRequest(name="Seam Test", owner_id=uuid.uuid4())
    )
    assert result.account_number.startswith("VIRT-")
    assert result.ifsc == "GOBN0001001"

    other = await adapter.create_account(
        LedgerAccountRequest(name="Seam Test 2", owner_id=uuid.uuid4())
    )
    assert other.account_number != result.account_number


@pytest.mark.asyncio
async def test_create_account_via_seam_keeps_response_shape(
    db_session: AsyncSession, super_admin: User
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await request_as(
            ac,
            super_admin.id,
            "POST",
            "/api/finance/accounts",
            json={
                "name": "Seam Account",
                "description": "via adapter",
                "owner_id": str(super_admin.id),
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Seam Account"
        assert data["account_number"].startswith("VIRT-")
        assert data["ifsc"] == "GOBN0001001"
        assert data["balance_paise"] == 0
