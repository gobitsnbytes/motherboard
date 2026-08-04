"""
Unit and integration tests for Internal Contract Assistant and OKF Rule Engine.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.llm_client import SparkCloudAIClient, get_llm_client
from app.services.okf_engine import DeterministicRuleEngine, get_okf_store


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
async def test_contract_assistant_autofix_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "clause_text": "Vendor shall provide uncapped liability for all damages.",
            "issue_description": "Uncapped liability is forbidden under company policy.",
            "tier": 1,
            "policy_tag": "liability",
        }
        response = await client.post("/api/contract-assistant/autofix", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == 1
        assert "IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY" in data["suggested_rewrite"]


@pytest.mark.asyncio
async def test_inbound_email_webhook_security():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "from_email": "counterparty@example.com",
            "subject": "Executed Vendor Agreement",
            "attachments_count": 1,
        }

        # 1. Valid token authentication
        valid_res = await client.post(
            "/api/contract-assistant/inbound-email",
            json=payload,
            headers={"x-inbound-secret": "inbound_sec_8f9a2b4c1d3e5f6g"},
        )
        assert valid_res.status_code == 200
        assert valid_res.json()["verified"] is True

        # 2. Unauthorized token authentication attempt
        invalid_res = await client.post(
            "/api/contract-assistant/inbound-email",
            json=payload,
            headers={"x-inbound-secret": "invalid_malicious_token_123"},
        )
        assert invalid_res.status_code == 401
        assert "Invalid webhook signature" in invalid_res.json()["detail"]
