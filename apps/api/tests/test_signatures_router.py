"""
Unit and integration tests for bnb-signatures engine and REST API.
"""

import io
import pytest
import uuid
from httpx import ASGITransport, AsyncClient
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import User
from conftest import internal_auth_headers, request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    doc.build([Paragraph("Test Contract Document Header", styles["Heading1"]), Paragraph("This is a sample legal contract for digital signature verification.", styles["Normal"])])
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_upload_contract_pdf(sample_pdf_bytes: bytes, super_admin):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("contract.pdf", sample_pdf_bytes, "application/pdf")}
        response = await request_as(client, super_admin.id, "POST", "/api/signatures/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert "file_path" in data
        assert data["page_count"] >= 1
        assert len(data["previews"]) >= 1
        assert data["previews"][0].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_signature_request_creation_and_signing_flow(db_session: AsyncSession, sample_pdf_bytes: bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create user
        user = User(display_name="Contract Creator", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        # 1. Upload
        files = {"file": ("nda_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        assert upload_res.status_code == 200
        file_path = upload_res.json()["file_path"]

        # 2. Create Request via API
        payload = {
            "title": "Non-Disclosure Agreement 2026",
            "file_path": file_path,
            "recipients": [
                {
                    "name": "Jane Doe",
                    "email": "jane@example.com",
                    "role": "signer",
                    "signing_order": 1,
                }
            ],
            "fields": [
                {
                    "recipient_id": str(uuid.uuid4()),
                    "type": "signature",
                    "page_number": 1,
                    "pos_x": 10.0,
                    "pos_y": 20.0,
                    "width": 30.0,
                    "height": 10.0,
                    "required": True,
                }
            ],
            "expires_in_days": 15,
        }

        create_res = await request_as(client, user.id, "POST", "/api/signatures/requests", json=payload)
        assert create_res.status_code == 200
        req_data = create_res.json()
        assert req_data["title"] == "Non-Disclosure Agreement 2026"
        assert len(req_data["recipients"]) == 1
        recipient_token = req_data["recipients"][0]["access_token"]
        field_id = req_data["fields"][0]["id"]

        # 3. Public Recipient Sign Portal View
        portal_res = await client.get(f"/api/signatures/sign/{recipient_token}")
        assert portal_res.status_code == 200
        portal_data = portal_res.json()
        assert portal_data["recipient"]["name"] == "Jane Doe"
        assert len(portal_data["previews"]) >= 1

        # 4. Submit Signature
        dummy_sig_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUheader"
        sign_res = await client.post(
            f"/api/signatures/sign/{recipient_token}",
            json={
                "fields": [
                    {"field_id": field_id, "value": dummy_sig_base64}
                ]
            }
        )
        assert sign_res.status_code == 200
        assert sign_res.json()["status"] == "success"
        assert sign_res.json()["request_status"] == "completed"

        # 5. Verify Authenticity Hash
        verify_res = await client.get(f"/api/signatures/verify/{req_data['id']}")
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["status"] == "completed"
        assert verify_data["completed_signatories"] == 1
        assert len(verify_data["audit_trail"]) >= 2


@pytest.mark.asyncio
async def test_public_verification_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/signatures/verify/non_existent_hash_123")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_signature_request_otp_verification_flow(db_session: AsyncSession, sample_pdf_bytes: bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="OTP Contract Admin", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        # Upload contract
        files = {"file": ("otp_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        # Create request requiring OTP
        payload = {
            "title": "High Security Agreement",
            "file_path": file_path,
            "recipients": [
                {
                    "name": "Akshat Kushwaha",
                    "email": "akshatkushwah@gmail.com",
                    "role": "signer",
                    "signing_order": 1,
                    "requires_otp": True,
                }
            ],
            "fields": [
                {
                    "recipient_id": str(uuid.uuid4()),
                    "type": "signature",
                    "page_number": 1,
                    "pos_x": 10.0,
                    "pos_y": 20.0,
                    "width": 30.0,
                    "height": 10.0,
                    "required": True,
                }
            ],
        }

        create_res = await request_as(client, user.id, "POST", "/api/signatures/requests", json=payload)
        assert create_res.status_code == 200
        req_data = create_res.json()
        recipient_token = req_data["recipients"][0]["access_token"]
        assert req_data["recipients"][0]["requires_otp"] is True

        # Check public portal endpoint returns masked email
        portal_res = await client.get(f"/api/signatures/sign/{recipient_token}")
        assert portal_res.status_code == 200
        portal_data = portal_res.json()
        assert portal_data["recipient"]["requires_otp"] is True
        assert "masked_email" in portal_data["recipient"]

        # Request OTP with wrong email -> fail
        bad_req = await client.post(f"/api/signatures/sign/{recipient_token}/request-otp", json={"email": "wrong@example.com"})
        assert bad_req.status_code == 400

        # Request OTP with correct email -> pass
        good_req = await client.post(f"/api/signatures/sign/{recipient_token}/request-otp", json={"email": "akshatkushwah@gmail.com"})
        assert good_req.status_code == 200
        assert good_req.json()["expires_in_seconds"] == 120

        # Fetch recipient to get generated code
        from sqlalchemy import select
        from app.db.models import SignatureRecipient
        res = await db_session.execute(select(SignatureRecipient).where(SignatureRecipient.access_token == recipient_token))
        recipient_db = res.scalar_one()
        assert recipient_db.otp_code is not None

        # Verify with wrong OTP -> fail
        wrong_verify = await client.post(f"/api/signatures/sign/{recipient_token}/verify-otp", json={"otp": "000000"})
        assert wrong_verify.status_code == 400

        # Verify with correct OTP -> pass
        right_verify = await client.post(f"/api/signatures/sign/{recipient_token}/verify-otp", json={"otp": recipient_db.otp_code})
        assert right_verify.status_code == 200
        assert right_verify.json()["success"] is True

