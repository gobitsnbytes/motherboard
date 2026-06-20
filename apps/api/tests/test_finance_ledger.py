"""
Integration tests for the Virtual Finance Ledger, money requests, limits validation, and card simulation.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import (
    User,
    VirtualAccount,
    VirtualCard,
    MoneyRequest,
    Grant,
)
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    """Fixture to override the database session dependency with the test session."""
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_finance_ledger_workflow(db_session: AsyncSession):
    """
    Test the virtual ledger workflow, including:
      - Creating virtual accounts.
      - Money request approvals causing ledger postings.
      - Generating transactions history list.
      - Enforcing card spending limits (daily, monthly, and balance checks) in charge simulations.
    """
    # 1. Create a test user (Finance Admin)
    admin_user = User(display_name="Finance Admin")
    db_session.add(admin_user)
    await db_session.commit()

    # Grant finance.admin permission to this user
    grant = Grant(
        principal_type="user",
        principal_id=admin_user.id,
        permission_key="finance.admin",
    )
    db_session.add(grant)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 2. Create two virtual accounts
        payload_acc1 = {
            "name": "Bangalore Operations",
            "description": "Virtual budgeting for Bangalore fork",
            "owner_id": str(admin_user.id)
        }
        res = await request_as(ac, admin_user.id, "POST", "/api/finance/accounts", json=payload_acc1)
        assert res.status_code == 201
        acc1 = res.json()
        acc1_id = acc1["id"]

        payload_acc2 = {
            "name": "Mumbai Operations",
            "description": "Virtual budgeting for Mumbai fork",
            "owner_id": str(admin_user.id)
        }
        res = await request_as(ac, admin_user.id, "POST", "/api/finance/accounts", json=payload_acc2)
        assert res.status_code == 201
        acc2 = res.json()
        acc2_id = acc2["id"]

        # Verify initial balances (0 paise)
        assert acc1["balance_paise"] == 0
        assert acc2["balance_paise"] == 0

        # 3. Create a Money Request from pool (from_account_id=None) to acc1
        payload_req = {
            "from_account_id": None,
            "to_account_id": acc1_id,
            "amount_paise": 100000, # ₹1000
            "description": "Initial pool budget injection"
        }
        res = await request_as(ac, admin_user.id, "POST", "/api/finance/requests", json=payload_req)
        assert res.status_code == 201
        req1 = res.json()

        # Approve the request to execute balance changes
        res = await request_as(
            ac,
            admin_user.id,
            "POST",
            f"/api/finance/requests/{req1['id']}/approve",
            json={"note": "Approved injection"},
        )
        assert res.status_code == 200

        # Verify balance of acc1 is updated
        res = await request_as(ac, admin_user.id, "GET", f"/api/finance/accounts/{acc1_id}")
        assert res.status_code == 200
        assert res.json()["balance_paise"] == 100000

        # Reject transfers from empty source accounts before any debit can occur.
        payload_empty_source_req = {
            "from_account_id": acc2_id,
            "to_account_id": acc1_id,
            "amount_paise": 50000,
            "description": "Invalid empty-source transfer",
        }
        res = await request_as(
            ac,
            admin_user.id,
            "POST",
            "/api/finance/requests",
            json=payload_empty_source_req,
        )
        assert res.status_code == 201
        empty_source_req = res.json()

        res = await request_as(
            ac,
            admin_user.id,
            "POST",
            f"/api/finance/requests/{empty_source_req['id']}/approve",
            json={"note": "Should fail"},
        )
        assert res.status_code == 400
        assert "Source account has insufficient balance" in res.json()["detail"]

        res = await request_as(ac, admin_user.id, "GET", f"/api/finance/accounts/{acc2_id}")
        assert res.status_code == 200
        assert res.json()["balance_paise"] == 0

        # Verify VirtualTransaction log was created
        res = await request_as(ac, admin_user.id, "GET", f"/api/finance/accounts/{acc1_id}/transactions")
        assert res.status_code == 200
        transactions = res.json()
        assert len(transactions) == 1
        assert transactions[0]["source_account_id"] is None
        assert transactions[0]["destination_account_id"] == acc1_id
        assert transactions[0]["amount_paise"] == 100000
        assert transactions[0]["reference_type"] == "money_request"
        assert transactions[0]["reference_id"] == req1["id"]

        # 4. Create a virtual card with limits for acc1
        payload_card = {
            "account_id": acc1_id,
            "holder_id": str(admin_user.id),
            "card_name": "Ops Petrol Card",
            "card_type": "virtual",
            "expires_month": 12,
            "expires_year": 2028,
            "daily_limit_paise": 50000, # ₹500
            "monthly_limit_paise": 200000 # ₹2000
        }
        res = await request_as(ac, admin_user.id, "POST", "/api/finance/cards", json=payload_card)
        assert res.status_code == 201
        card = res.json()
        card_id = card["id"]

        # Verify limit fields exist in card response
        assert card["daily_limit_paise"] == 50000
        assert card["monthly_limit_paise"] == 200000

        # 5. Simulate card charges
        # Case A: Charge within limits (₹300 / 30000 paise)
        payload_charge = {
            "amount_paise": 30000,
            "merchant": "Shell Fuel",
            "description": "Weekly fuel refilling"
        }
        res = await request_as(
            ac,
            admin_user.id,
            "POST",
            f"/api/finance/cards/{card_id}/simulate-charge",
            json=payload_charge,
        )
        assert res.status_code == 200
        charge_tx = res.json()
        assert charge_tx["amount_paise"] == 30000
        assert charge_tx["reference_type"] == "card_charge"

        # Verify balance of acc1 was reduced (100000 - 30000 = 70000)
        res = await request_as(ac, admin_user.id, "GET", f"/api/finance/accounts/{acc1_id}")
        assert res.json()["balance_paise"] == 70000

        # Case B: Charge exceeding daily limit (₹300 more, total ₹600, limit is ₹500)
        payload_excess_charge = {
            "amount_paise": 30000,
            "merchant": "BP Fuel",
            "description": "Extra fuel purchase"
        }
        res = await request_as(
            ac,
            admin_user.id,
            "POST",
            f"/api/finance/cards/{card_id}/simulate-charge",
            json=payload_excess_charge,
        )
        assert res.status_code == 400
        assert "exceeds daily limit" in res.json()["detail"]

        # Case C: Charge exceeding account balance (₹800 charge, balance is ₹700)
        payload_excess_balance = {
            "amount_paise": 80000,
            "merchant": "Apple Store",
            "description": "Mock MacBook upgrade"
        }
        res = await request_as(
            ac,
            admin_user.id,
            "POST",
            f"/api/finance/cards/{card_id}/simulate-charge",
            json=payload_excess_balance,
        )
        assert res.status_code == 400
        assert "Insufficient balance" in res.json()["detail"]

        # 6. Verify global transactions feed
        res = await request_as(ac, admin_user.id, "GET", "/api/finance/transactions")
        assert res.status_code == 200
        all_tx = res.json()
        # Should contain the money_request injection and the successful Shell fuel card charge
        assert len(all_tx) == 2
        ref_types = [tx["reference_type"] for tx in all_tx]
        assert "money_request" in ref_types
        assert "card_charge" in ref_types
