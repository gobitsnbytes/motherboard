"""
Unit and integration tests for Internal Contract Assistant and OKF Rule Engine.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_session
from app.services.llm_client import SparkCloudAIClient, get_llm_client
from app.services.okf_engine import DeterministicRuleEngine, get_okf_store
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


def test_okf_knowledge_store_and_rule_engine():
    store = get_okf_store()
    rules = store.get_rules()
    assert len(rules) >= 1

    rule_engine = DeterministicRuleEngine(store)
    # Test uncapped liability detection
    findings = rule_engine.evaluate_clause("§8.1", "Limitation of Liability", "Vendor shall provide uncapped liability for all damages.")
    assert len(findings) >= 1
    assert findings[0]["severity"] == "high"

    # Test payment terms threshold
    payment_findings = rule_engine.evaluate_clause("§3.2", "Payment Terms", "Invoices shall be payable within Net 90 days.")
    assert len(payment_findings) >= 1
    assert payment_findings[0]["severity"] == "medium"


def test_sparkcloud_ai_client_configuration():
    client = get_llm_client()
    if client.api_key:
        assert client.api_key.startswith("sc-ai-")
    assert "sparkden.org" in client.base_url or "cloud.sparkden.org" in client.base_url
    assert client.model == "auto"


@pytest.mark.asyncio
async def test_contract_assistant_rules_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/contract-assistant/rules")
        assert response.status_code == 200
        data = response.json()
        assert "total_rules" in data
        assert data["total_rules"] >= 1


@pytest.mark.asyncio
async def test_contract_assistant_autofix_endpoint(super_admin: User):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "clause_text": "Vendor shall provide uncapped liability for all damages.",
            "issue_description": "Uncapped liability is forbidden under company policy.",
            "tier": 1,
            "policy_tag": "liability",
        }
        response = await request_as(client, super_admin.id, "POST", "/api/contract-assistant/autofix", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == 1
        assert "IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY" in data["suggested_rewrite"]


@pytest.mark.asyncio
async def test_inbound_email_webhook_security(monkeypatch):
    monkeypatch.setenv("INBOUND_EMAIL_WEBHOOK_SECRET", "inbound_sec_8f9a2b4c1d3e5f6g")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        valid_payload = {
            "from_email": "legal@gobitsnbytes.org",
            "subject": "Executed Vendor Agreement",
            "attachments_count": 1,
        }

        # 1. Valid token + authorized domain
        valid_res = await client.post(
            "/api/contract-assistant/inbound-email",
            json=valid_payload,
            headers={"x-inbound-secret": "inbound_sec_8f9a2b4c1d3e5f6g"},
        )
        assert valid_res.status_code == 200
        assert valid_res.json()["verified"] is True

        # 2. Unauthorized sender domain
        unauthorized_domain_payload = {
            "from_email": "attacker@externaldomain.com",
            "subject": "Malicious Attachment",
            "attachments_count": 1,
        }
        unauth_res = await client.post(
            "/api/contract-assistant/inbound-email",
            json=unauthorized_domain_payload,
            headers={"x-inbound-secret": "inbound_sec_8f9a2b4c1d3e5f6g"},
        )
        assert unauth_res.status_code == 401
        assert "Access Denied" in unauth_res.json()["detail"]

        # 3. Unauthorized secret token attempt
        invalid_res = await client.post(
            "/api/contract-assistant/inbound-email",
            json=valid_payload,
            headers={"x-inbound-secret": "invalid_malicious_token_123"},
        )
        assert invalid_res.status_code == 401
        assert "Invalid webhook signature" in invalid_res.json()["detail"]


@pytest.mark.asyncio
async def test_contract_assistant_database_crud_and_dispatch(super_admin: User, db_session: AsyncSession):
    from app.db.models import ContractAssistantContract, ContractAssistantFinding, ContractAssistantClause

    # 1. Seed a DB contract directly
    c = ContractAssistantContract(
        title="Master Vendor Service Level Agreement",
        counterparty="Acme Cloud Solutions",
        status="in_review",
        value="₹10,00,000",
        created_by=super_admin.id,
    )
    db_session.add(c)
    await db_session.flush()

    cl = ContractAssistantClause(
        contract_id=c.id,
        ref="§8.1",
        heading="Limitation of Liability",
        text="Vendor shall provide uncapped liability for all system outages.",
        page_number=1,
    )
    db_session.add(cl)
    await db_session.flush()

    f = ContractAssistantFinding(
        contract_id=c.id,
        clause_id=cl.id,
        clause_ref="§8.1",
        heading="Limitation of Liability",
        source="rule_engine",
        severity="high",
        risk_type="Uncapped Liability",
        plain_english="Uncapped liability exposes company to unlimited financial risk.",
        suggested_action="Cap liability at contract fees.",
        tier=1,
        status="open",
    )
    db_session.add(f)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 2. Test GET /api/contract-assistant/contracts
        list_res = await client.get("/api/contract-assistant/contracts")
        assert list_res.status_code == 200
        contracts = list_res.json()
        assert len(contracts) >= 1
        found = next((item for item in contracts if item["id"] == str(c.id)), None)
        assert found is not None
        assert found["title"] == "Master Vendor Service Level Agreement"
        assert found["highest_risk"] == "high"

        # 3. Test GET /api/contract-assistant/contracts/{id}
        detail_res = await client.get(f"/api/contract-assistant/contracts/{c.id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert detail_data["title"] == "Master Vendor Service Level Agreement"
        assert len(detail_data["findings"]) == 1
        assert detail_data["findings"][0]["severity"] == "high"

        # 4. Attempt dispatch before resolving high-severity finding (Should fail due to safety gate)
        dispatch_blocked_res = await client.post(
            "/api/contract-assistant/dispatch",
            json={
                "contract_id": str(c.id),
                "recipients": [{"name": "Akshat", "email": "akshat@gobitsnbytes.org", "role": "signer"}],
            },
        )
        assert dispatch_blocked_res.status_code == 400
        assert "high-severity legal finding" in dispatch_blocked_res.json()["detail"]

        # 5. Resolve high-severity finding via PATCH endpoint
        patch_res = await client.patch(
            f"/api/contract-assistant/contracts/{c.id}/findings/{f.id}",
            json={"status": "resolved", "suggested_rewrite": "Liability is capped at ₹5,00,000."},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["finding_status"] == "resolved"

        # 6. Dispatch contract to bnb-signatures after resolving finding
        dispatch_success_res = await client.post(
            "/api/contract-assistant/dispatch",
            json={
                "contract_id": str(c.id),
                "recipients": [{"name": "Akshat Kushwaha", "email": "akshat@gobitsnbytes.org", "role": "signer"}],
            },
        )
        assert dispatch_success_res.status_code == 200
        dispatch_data = dispatch_success_res.json()
        assert dispatch_data["status"] == "dispatched"
        assert "signature_request_id" in dispatch_data

        # 7. Test verification page endpoint with contract ID
        verify_res = await client.get(f"/api/signatures/verify/{c.id}")
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["title"] == "Master Vendor Service Level Agreement"

