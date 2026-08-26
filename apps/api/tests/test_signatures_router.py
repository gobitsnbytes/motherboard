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


@pytest.mark.asyncio
async def test_contract_compliance_check(db_session: AsyncSession, sample_pdf_bytes: bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="Compliance Evaluator", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        # Upload & create contract
        files = {"file": ("comp_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Board Resolution & Governance Agreement",
            "file_path": file_path,
            "recipients": [
                {
                    "name": "Akshat Kushwaha",
                    "email": "akshat@gobitsnbytes.org",
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
        req_id = create_res.json()["id"]

        # Call compliance check
        comp_res = await client.get(f"/api/signatures/requests/{req_id}/compliance-check")
        assert comp_res.status_code == 200
        comp_data = comp_res.json()
        assert comp_data["compliance_score"] >= 80
        assert comp_data["overall_status"] == "compliant"
        assert len(comp_data["checks"]) == 6
        check_keys = [c["key"] for c in comp_data["checks"]]
        assert "it_act_sec10a" in check_keys
        assert "bsa_sec65b_audit_seal" in check_keys
        assert "dpdp_act_2023" in check_keys
        assert "section8_governance" in check_keys


@pytest.mark.asyncio
async def test_file_upload_verification(db_session: AsyncSession, sample_pdf_bytes: bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="File Verifier", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        # 1. Upload & create contract
        files = {"file": ("sample_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Tamper Verification Document",
            "file_path": file_path,
            "recipients": [
                {
                    "name": "Signer A",
                    "email": "signer@example.com",
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
        }
        create_res = await request_as(client, user.id, "POST", "/api/signatures/requests", json=payload)
        req_id = create_res.json()["id"]

        # 2. Test verify uploaded original file -> authentic
        verify_file_res = await client.post(
            "/api/signatures/verify/file",
            files={"file": ("sample_contract.pdf", sample_pdf_bytes, "application/pdf")},
        )
        assert verify_file_res.status_code == 200
        vf_data = verify_file_res.json()
        assert vf_data["is_authentic"] is True
        assert str(vf_data["document_id"]) == str(req_id)

        # 3. Test verify altered/unregistered file -> not authentic
        fake_bytes = b"%PDF-1.4 Fake altered content not in database"
        fake_verify_res = await client.post(
            "/api/signatures/verify/file",
            files={"file": ("altered.pdf", fake_bytes, "application/pdf")},
        )
        assert fake_verify_res.status_code == 200
        fake_data = fake_verify_res.json()
        assert fake_data["is_authentic"] is False
        assert fake_data["match_type"] == "unregistered"


@pytest.mark.asyncio
async def test_void_signature_request_blocks_signing(db_session: AsyncSession, sample_pdf_bytes: bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="Void Admin", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        # Create request
        files = {"file": ("void_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Contract To Be Voided",
            "file_path": file_path,
            "recipients": [
                {
                    "name": "Signer Void",
                    "email": "signer.void@example.com",
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
        req_data = create_res.json()
        req_id = req_data["id"]
        token = req_data["recipients"][0]["access_token"]
        field_id = req_data["fields"][0]["id"]

        # Void the contract
        void_res = await client.post(f"/api/signatures/requests/{req_id}/void")
        assert void_res.status_code == 200
        assert void_res.json()["status"] == "voided"

        # Attempt to request OTP on voided contract -> should fail (400)
        otp_res = await client.post(f"/api/signatures/sign/{token}/request-otp", json={"email": "signer.void@example.com"})
        assert otp_res.status_code == 400

        # Attempt to sign voided contract -> should fail (400)
        sign_res = await client.post(
            f"/api/signatures/sign/{token}",
            json={"fields": [{"field_id": field_id, "value": "data:image/png;base64,sample"}]},
        )
        assert sign_res.status_code == 400

        # Verify endpoint reflects voided status
        verify_res = await client.get(f"/api/signatures/verify/{req_id}")
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "voided"

        # Export voided copy
        export_res = await client.get(f"/api/signatures/requests/{req_id}/export-void")
        assert export_res.status_code == 200
        assert "OFFICIAL CERTIFICATE OF CANCELLATION" in export_res.text


@pytest.mark.asyncio
async def test_delete_signature_request_permanently(db_session: AsyncSession, sample_pdf_bytes: bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="Delete Admin", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        # Create request
        files = {"file": ("delete_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Contract To Be Purged",
            "file_path": file_path,
            "recipients": [
                {
                    "name": "Signer Purge",
                    "email": "signer.purge@example.com",
                    "role": "signer",
                    "signing_order": 1,
                }
            ],
            "fields": [],
        }
        create_res = await request_as(client, user.id, "POST", "/api/signatures/requests", json=payload)
        req_id = create_res.json()["id"]

        # Delete permanently
        del_res = await client.delete(f"/api/signatures/requests/{req_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify not found after delete
        verify_res = await client.get(f"/api/signatures/verify/{req_id}")
        assert verify_res.status_code == 404




@pytest.mark.asyncio
async def test_audit_trail_endpoint_and_response_inclusion(db_session: AsyncSession, sample_pdf_bytes: bytes):
    """GET /requests/{id}/audit returns the full chronological audit trail, and
    SignatureRequestResponse now embeds audit_logs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="Audit Viewer", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        files = {"file": ("audit_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Audited Contract",
            "file_path": file_path,
            "recipients": [
                {"name": "Signer A", "email": "a@example.com", "role": "signer", "signing_order": 1}
            ],
            "fields": [],
        }
        create_res = await request_as(client, user.id, "POST", "/api/signatures/requests", json=payload)
        req_id = create_res.json()["id"]
        assert create_res.json()["audit_logs"], "created event must be embedded in response"

        audit_res = await request_as(client, user.id, "GET", f"/api/signatures/requests/{req_id}/audit")
        assert audit_res.status_code == 200
        body = audit_res.json()
        assert body["request_id"] == req_id
        actions = [e["action"] for e in body["entries"]]
        assert "created" in actions


@pytest.mark.asyncio
async def test_org_countersign_flow(db_session: AsyncSession, sample_pdf_bytes: bytes):
    """requires_org_countersign appends legal@ org_signer; countersign endpoint seals
    with IAM permission; completion fires only when all signers executed."""
    from unittest.mock import patch, MagicMock

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = User(display_name="Org Seal Admin", is_super_admin=True)
        db_session.add(user)
        await db_session.commit()

        files = {"file": ("org_contract.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, user.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Partnership MoU (org counter-signed)",
            "file_path": file_path,
            "recipients": [
                {"name": "External Partner", "email": "partner@example.com", "role": "signer", "signing_order": 1}
            ],
            "fields": [],
            "requires_org_countersign": True,
        }
        create_res = await request_as(client, user.id, "POST", "/api/signatures/requests", json=payload)
        req_data = create_res.json()
        roles = {r["role"]: r for r in req_data["recipients"]}
        assert "org_signer" in roles
        assert roles["org_signer"]["email"] == "legal@gobitsnbytes.org"
        org_recipient = roles["org_signer"]
        partner = roles["signer"]

        # Countersign before external party -> permitted but not finalizing
        cs_res = await request_as(
            client, user.id, "POST", f"/api/signatures/requests/{req_data['id']}/countersign",
            json={"note": "Approved under Board delegation 2026-04."},
        )
        assert cs_res.status_code == 200

        # External partner signs via public token flow (mock the PDF seal writer)
        with patch("app.routers.signatures.embed_signatures_and_seal") as mock_seal:
            mock_seal.return_value = (b"%PDF-1.4 sealed", "deadbeef" * 8)
            sign_res = await client.post(
                f"/api/signatures/sign/{partner['access_token']}",
                json={"fields": []},
            )
        assert sign_res.status_code == 200, f"SIGN FAIL: {sign_res.text[:400]}"
        assert sign_res.json()["request_status"] == "completed"

        from sqlalchemy import select as _sel
        from app.db.models import SignatureAuditLog as _SAL
        rows = (
            await db_session.execute(_sel(_SAL).where(_SAL.request_id == uuid.UUID(req_data["id"])))
        ).scalars().all()
        verify_res = await client.get(f"/api/signatures/verify/{req_data['id']}")
        assert verify_res.status_code == 200
        vdata = verify_res.json()
        audit_actions = [e["action"] for e in vdata["audit_trail"]] + [r.action for r in rows]
        assert vdata["status"] == "completed"
        assert "signed_org_countersign" in audit_actions
        assert "completed" in audit_actions


@pytest.mark.asyncio
async def test_countersign_rejected_without_permission(db_session: AsyncSession, sample_pdf_bytes: bytes):
    """A non-super-admin without the signatures.countersign grant cannot countersign."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = User(display_name="Admin Holder", is_super_admin=True)
        plain = User(display_name="Plain Member", is_super_admin=False)
        db_session.add_all([admin, plain])
        await db_session.commit()

        files = {"file": ("denied.pdf", sample_pdf_bytes, "application/pdf")}
        upload_res = await request_as(client, admin.id, "POST", "/api/signatures/upload", files=files)
        file_path = upload_res.json()["file_path"]

        payload = {
            "title": "Deny Me",
            "file_path": file_path,
            "recipients": [],
            "fields": [],
            "requires_org_countersign": True,
        }
        create_res = await request_as(client, admin.id, "POST", "/api/signatures/requests", json=payload)
        req_id = create_res.json()["id"]

        denied = await request_as(
            client, plain.id, "POST", f"/api/signatures/requests/{req_id}/countersign",
            json={"note": None},
        )
        assert denied.status_code == 403
