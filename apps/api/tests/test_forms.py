from httpx import ASGITransport, AsyncClient
import csv
import io
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.main import app
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_forms_validate_answers_and_return_labeled_responses(super_admin):
    super_admin_id = super_admin.id
    blocks = [
        {"id": "name", "type": "text", "label": "Your name", "required": True},
        {"id": "track", "type": "select", "label": "Track", "required": True, "options": ["Design", "Code"]},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(client, super_admin_id, "POST", "/api/forms", json={"title": "Interest form", "slug": "interest-form", "blocks": blocks, "is_published": True})
        assert created.status_code == 201, created.text
        form_id = created.json()["id"]

        invalid = await client.post("/api/forms/public/interest-form/submissions", headers={"Idempotency-Key": "invalid-answer-key-001"}, json={"answers": {"unknown": "value"}, "accepted_terms": True})
        assert invalid.status_code == 422

        headers = {"Idempotency-Key": "valid-answer-key-0001"}
        submitted = await client.post("/api/forms/public/interest-form/submissions", headers=headers, json={"answers": {"name": "Asha", "track": "Code"}, "accepted_terms": True})
        assert submitted.status_code == 201, submitted.text
        assert submitted.json()["upload_token"]

        retried = await client.post("/api/forms/public/interest-form/submissions", headers=headers, json={"answers": {"name": "Asha", "track": "Code"}, "accepted_terms": True})
        assert retried.status_code == 200, retried.text
        assert retried.json()["id"] == submitted.json()["id"]
        assert retried.json()["status"] == "already_submitted"

        mismatched = await client.post("/api/forms/public/interest-form/submissions", headers=headers, json={"answers": {"name": "Someone else", "track": "Design"}, "accepted_terms": True})
        assert mismatched.status_code == 409

        responses = await request_as(client, super_admin_id, "GET", f"/api/forms/{form_id}/submissions")
        assert responses.status_code == 200, responses.text
        assert len(responses.json()) == 1
        assert responses.json()[0]["answers"] == {"name": "Asha", "track": "Code"}
        assert responses.json()[0]["labels"] == {"name": "Your name", "track": "Track"}

        formula = await client.post(
            "/api/forms/public/interest-form/submissions",
            headers={"Idempotency-Key": "formula-answer-key-0001"},
            json={"answers": {"name": "=1+1", "track": "Design"}, "accepted_terms": True},
        )
        assert formula.status_code == 201

        exported = await request_as(client, super_admin_id, "GET", f"/api/forms/{form_id}/submissions/export.csv")
        assert exported.status_code == 200
        assert "attachment;" in exported.headers["content-disposition"]
        csv_rows = list(csv.reader(io.StringIO(exported.text.lstrip("\ufeff"))))
        assert csv_rows[0][3:5] == ["Your name", "Track"]
        assert csv_rows[1][3:5] == ["Asha", "Code"]
        assert csv_rows[2][3] == "'=1+1"


@pytest.mark.asyncio
async def test_form_uploads_require_token_and_are_idempotent(super_admin, tmp_path, monkeypatch):
    from app.routers import forms

    monkeypatch.setattr(forms, "UPLOAD_DIR", str(tmp_path))
    blocks = [{"id": "proof", "type": "file", "label": "Proof", "required": True}]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(client, super_admin.id, "POST", "/api/forms", json={"title": "Upload form", "slug": "upload-form", "blocks": blocks, "is_published": True})
        receipt = await client.post(
            "/api/forms/public/upload-form/submissions",
            headers={"Idempotency-Key": "upload-attempt-key-0001"},
            json={"answers": {}, "accepted_terms": True},
        )
        assert receipt.status_code == 201
        upload_path = f"/api/forms/public/submissions/{receipt.json()['id']}/uploads"
        file_args = {"files": {"file": ("proof.pdf", b"%PDF-1.7\nsame-content", "application/pdf")}, "data": {"field_id": "proof"}}
        upload_headers = {"X-Form-Upload-Token": receipt.json()["upload_token"]}
        incomplete = await client.post(
            f"/api/forms/public/submissions/{receipt.json()['id']}/complete",
            headers=upload_headers,
        )
        assert incomplete.status_code == 422
        unauthorized = await client.post(upload_path, **file_args)
        assert unauthorized.status_code == 401
        first = await client.post(upload_path, headers=upload_headers, **file_args)
        duplicate = await client.post(upload_path, headers=upload_headers, **file_args)
        assert first.status_code == 201, first.text
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["id"] == first.json()["id"]
        completed = await client.post(
            f"/api/forms/public/submissions/{receipt.json()['id']}/complete",
            headers=upload_headers,
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["intake_status"] == "complete"
