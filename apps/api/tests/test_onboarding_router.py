from datetime import datetime, timezone
import uuid
from types import SimpleNamespace

from sqlalchemy import select

from app.config import get_settings
from app.db.models import (
    AuditLog,
    DiscordAccount,
    Grant,
    Group,
    Membership,
    OnboardingCase,
    OnboardingDocument,
    OnboardingParticipant,
    SignatureAuditLog,
    SignatureRecipient,
    SignatureRequest,
    User,
)
from conftest import request_as


async def test_list_cases_serializes_before_commit(monkeypatch):
    """A commit expires ORM state in production, so responses must exist first."""
    from app.routers import onboarding

    events: list[str] = []
    case = SimpleNamespace(id=uuid.uuid4())

    class _Scalars:
        def all(self):
            return [case]

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Db:
        async def execute(self, _statement):
            return _Result()

        async def flush(self):
            events.append("flush")

        async def commit(self):
            events.append("commit")

    async def _allow(*_args):
        return None

    async def _load(_db, _case_id):
        return case

    async def _sync(_db, _case):
        return None

    def _serialize(_case):
        events.append("serialize")
        return "response"

    monkeypatch.setattr(onboarding, "require_permission", _allow)
    monkeypatch.setattr(onboarding, "_load_case", _load)
    monkeypatch.setattr(onboarding, "_sync_signature_states", _sync)
    monkeypatch.setattr(onboarding, "_case_response", _serialize)

    result = await onboarding.list_cases(_Db(), SimpleNamespace(user_id=uuid.uuid4()))

    assert result == ["response"]
    assert events == ["flush", "serialize", "commit"]


async def test_volunteer_case_creates_scoped_portal(super_admin, db_session, client):
    get_settings().smtp_host = None
    response = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Asha volunteer onboarding",
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["current_revision_id"]
    assert all(
        document["revision_id"] == body["current_revision_id"]
        for document in body["documents"]
    )
    portal_url = body["participants"][0]["portal_url"]
    token = portal_url.rsplit("/", 1)[-1]
    portal = await client.get(f"/api/onboarding/public/{token}")
    assert portal.status_code == 200
    assert portal.json()["participant"]["email"] == "asha@example.com"
    audit_actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "onboarding.case_created" in audit_actions


async def test_assigned_reviewer_is_independent_and_records_the_active_revision(
    super_admin, db_session, client
):
    get_settings().smtp_host = None
    reviewer = User(display_name="Independent Reviewer", is_super_admin=True)
    executive = Group(slug="sg_executive", name="Executive Leadership", is_system=True)
    db_session.add_all([reviewer, executive])
    await db_session.flush()
    db_session.add(
        Grant(
            principal_type="user",
            principal_id=reviewer.id,
            permission_key="onboarding.review",
        )
    )
    db_session.add_all(
        [
            DiscordAccount(
                user_id=super_admin.id,
                discord_id="123456789012345670",
                username="casecreator",
                last_synced_at=datetime.now(timezone.utc),
            ),
            DiscordAccount(
                user_id=reviewer.id,
                discord_id="123456789012345671",
                username="reviewer",
                last_synced_at=datetime.now(timezone.utc),
            ),
            Membership(
                user_id=super_admin.id, group_id=executive.id, source="discord_sync"
            ),
            Membership(
                user_id=reviewer.id, group_id=executive.id, source="discord_sync"
            ),
        ]
    )
    db_session.add(
        Grant(
            principal_type="user",
            principal_id=super_admin.id,
            permission_key="onboarding.review",
        )
    )
    await db_session.commit()
    self_assignment = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Invalid reviewer",
            "reviewer_id": str(super_admin.id),
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    assert self_assignment.status_code == 201
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Independent review",
            "reviewer_id": str(reviewer.id),
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    reviewed = await request_as(
        client,
        reviewer.id,
        "POST",
        f"/api/onboarding/cases/{case_id}/review",
        json={
            "decision": "changes_requested",
            "note": "Please correct the packet details.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviews"][0]["decision"] == "changes_requested"


async def test_reviewer_list_requires_permission_and_discord_link(
    super_admin, db_session, client
):
    legacy_admin = User(
        display_name="Legacy Admin",
        email="legacy@example.com",
        is_super_admin=True,
    )
    clushed = User(display_name="Clushed✦", email="yashsinghv2770@gmail.com")
    aero = User(display_name="Aero", email="akshatsingh14372@outlook.com")
    executive = Group(slug="sg_executive", name="Executive Leadership", is_system=True)
    db_session.add_all([legacy_admin, clushed, aero, executive])
    await db_session.flush()
    db_session.add_all(
        [
            Grant(
                principal_type="user",
                principal_id=clushed.id,
                permission_key="onboarding.review",
            ),
            Grant(
                principal_type="user",
                principal_id=aero.id,
                permission_key="onboarding.review",
            ),
            DiscordAccount(
                user_id=clushed.id,
                discord_id="123456789012345678",
                username="wellitsclushed",
                last_synced_at=datetime.now(timezone.utc),
            ),
            DiscordAccount(
                user_id=aero.id,
                discord_id="223456789012345678",
                username="a3rodev",
                last_synced_at=datetime.now(timezone.utc),
            ),
            Membership(
                user_id=clushed.id, group_id=executive.id, source="discord_sync"
            ),
            Membership(user_id=aero.id, group_id=executive.id, source="discord_sync"),
        ]
    )
    await db_session.commit()

    response = await request_as(
        client,
        super_admin.id,
        "GET",
        "/api/onboarding/reviewers",
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(aero.id),
            "display_name": "Aero",
            "email": "akshatsingh14372@outlook.com",
            "avatar_url": None,
            "title": None,
            "discord_username": "a3rodev",
        },
        {
            "id": str(clushed.id),
            "display_name": "Clushed✦",
            "email": "yashsinghv2770@gmail.com",
            "avatar_url": None,
            "title": None,
            "discord_username": "wellitsclushed",
        },
    ]


async def test_minor_requires_parent_and_underage_is_rejected(super_admin, client):
    minor = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Minor volunteer",
            "participant": {
                "name": "Minor Example",
                "email": "minor@example.com",
                "date_of_birth": "2010-04-02",
            },
        },
    )
    assert minor.status_code == 422
    underage = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Too young",
            "participant": {
                "name": "Child Example",
                "email": "child@example.com",
                "date_of_birth": "2015-04-02",
            },
        },
    )
    assert underage.status_code == 422


async def test_fork_lead_invites_minor_teammate_with_separate_guardian_packet(
    super_admin, db_session, client
):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "fork",
            "title": "Chennai fork onboarding",
            "fork_name": "Chennai",
            "participant": {
                "name": "Adult Lead",
                "email": "lead@example.com",
                "date_of_birth": "2000-01-01",
            },
        },
    )
    assert created.status_code == 201, created.text
    token = created.json()["participants"][0]["portal_url"].rsplit("/", 1)[-1]
    invite_payload = {
        "name": "Minor Teammate",
        "email": "minor-teammate@example.com",
        "date_of_birth": "2010-08-02",
        "parent": {"name": "Guardian Example", "email": "guardian@example.com"},
    }
    blocked = await client.post(
        f"/api/onboarding/public/{token}/teammates", json=invite_payload
    )
    assert blocked.status_code == 403

    lead = (
        await db_session.execute(
            select(OnboardingParticipant).where(
                OnboardingParticipant.email == "lead@example.com"
            )
        )
    ).scalar_one()
    documents = (
        (
            await db_session.execute(
                select(OnboardingDocument).where(
                    OnboardingDocument.participant_id == lead.id
                )
            )
        )
        .scalars()
        .all()
    )
    for document in documents:
        document.status = "review_requested"
    lead.status = "under_review"
    await db_session.commit()

    invited = await client.post(
        f"/api/onboarding/public/{token}/teammates", json=invite_payload
    )
    assert invited.status_code == 201, invited.text
    body = invited.json()
    assert body["email_sent"] is False
    assert {invitee["role"] for invitee in body["invitees"]} == {"teammate", "parent"}

    guardian = (
        await db_session.execute(
            select(OnboardingParticipant).where(
                OnboardingParticipant.email == "guardian@example.com"
            )
        )
    ).scalar_one()
    guardian_document = (
        await db_session.execute(
            select(OnboardingDocument).where(
                OnboardingDocument.participant_id == guardian.id
            )
        )
    ).scalar_one()
    assert guardian_document.template_filename == "2_Parents_Consent_.docx"
    assert guardian_document.field_values["bnb.parent.minor_name"] == "Minor Teammate"
    assert guardian_document.field_values["bnb.parent.fork_name"] == "Chennai"
    onboarding_case = await db_session.get(OnboardingCase, guardian.case_id)
    assert onboarding_case.case_data["guardian_links"][str(guardian.id)]


async def test_staff_can_correct_untouched_volunteer_email_and_rotates_portal_link(
    super_admin, client
):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Email correction",
            "participant": {
                "name": "Asha Example",
                "email": "wrong@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    body = created.json()
    old_url = body["participants"][0]["portal_url"]
    old_token = old_url.rsplit("/", 1)[-1]
    updated = await request_as(
        client,
        super_admin.id,
        "PATCH",
        f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/email",
        json={"email": "correct@example.com"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["email"] == "correct@example.com"
    old_portal = await client.get(f"/api/onboarding/public/{old_token}")
    assert old_portal.status_code == 404
    new_token = updated.json()["portal_url"].rsplit("/", 1)[-1]
    portal = await client.get(f"/api/onboarding/public/{new_token}")
    assert portal.status_code == 200
    assert portal.json()["participant"]["email"] == "correct@example.com"


async def test_staff_can_resend_untouched_invite_and_rotates_portal_link(
    super_admin, client
):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "fork",
            "title": "Fork invite resend",
            "fork_name": "Chennai",
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    body = created.json()
    old_token = body["participants"][0]["portal_url"].rsplit("/", 1)[-1]
    resent = await request_as(
        client,
        super_admin.id,
        "POST",
        f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/resend",
    )
    assert resent.status_code == 200, resent.text
    assert resent.json()["email_sent"] is False
    assert (await client.get(f"/api/onboarding/public/{old_token}")).status_code == 404
    new_token = resent.json()["portal_url"].rsplit("/", 1)[-1]
    assert (await client.get(f"/api/onboarding/public/{new_token}")).status_code == 200


async def test_staff_can_cancel_onboarding_and_revoke_portal_link(
    super_admin, db_session, client
):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Cancelled volunteer onboarding",
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    token = body["participants"][0]["portal_url"].rsplit("/", 1)[-1]
    cancelled = await request_as(
        client,
        super_admin.id,
        "POST",
        f"/api/onboarding/cases/{body['id']}/cancel",
        json={"reason": "Participant asked to withdraw from onboarding."},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "revoked"
    assert (await client.get(f"/api/onboarding/public/{token}")).status_code == 404
    from app.db.models import AuditLog

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "onboarding.case_cancelled")
        )
    ).scalar_one()
    assert audit.target_id == body["id"]


async def test_staff_cannot_correct_email_after_packet_submission(super_admin, client):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Started packet",
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    body = created.json()
    token = body["participants"][0]["portal_url"].rsplit("/", 1)[-1]
    document_id = body["documents"][0]["id"]
    editor = (
        await client.get(
            f"/api/onboarding/public/{token}/documents/{document_id}/editor"
        )
    ).json()
    values = {}
    for field in editor["fields"]:
        if field["type"] == "signature":
            continue
        if field["type"] == "checkbox":
            values[field["id"]] = True
        elif field["type"] == "choice":
            values[field["id"]] = field["options"][0]
        elif field["type"] == "email":
            values[field["id"]] = "asha@example.com"
        elif field["type"] == "date":
            values[field["id"]] = "2026-09-19"
        elif field["type"] == "tel":
            values[field["id"]] = "9876543210"
        else:
            values[field["id"]] = "Test value"
    saved = await client.patch(
        f"/api/onboarding/public/{token}/documents/{document_id}/draft",
        json={
            "base_revision": editor["document"]["current_revision"],
            "values": values,
        },
    )
    assert saved.status_code == 200, saved.text
    submitted = await client.post(
        f"/api/onboarding/public/{token}/documents/{document_id}/submit",
        json={
            "base_revision": saved.json()["document"]["current_revision"],
            "confirmed_identity": True,
        },
    )
    assert submitted.status_code == 200, submitted.text
    updated = await request_as(
        client,
        super_admin.id,
        "PATCH",
        f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/email",
        json={"email": "correct@example.com"},
    )
    assert updated.status_code == 409


async def test_staff_can_rollback_an_unsigned_onboarding_signature_request(
    super_admin, db_session, client
):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "Signing repair",
            "participant": {
                "name": "Asha Example",
                "email": "asha@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    body = created.json()
    document = await db_session.get(
        OnboardingDocument, uuid.UUID(body["documents"][0]["id"])
    )
    request = SignatureRequest(
        title="Signing repair",
        status="pending",
        original_file_path="/tmp/signing-repair.pdf",
    )
    db_session.add(request)
    await db_session.flush()
    recipient = SignatureRecipient(
        request_id=request.id,
        name="Asha Example",
        email="asha@example.com",
        role="subject",
        status="pending",
        access_token="rollback-token",
        otp_hash="temporary",
    )
    db_session.add(recipient)
    await db_session.flush()
    document.status = "signing"
    document.signature_request_id = request.id
    document_id = document.id
    request_id = request.id
    recipient_id = recipient.id
    await db_session.commit()

    rolled_back = await request_as(
        client,
        super_admin.id,
        "POST",
        f"/api/onboarding/cases/{body['id']}/documents/{document_id}/rollback-signing",
        json={"reason": "The generated PDF repeated a multiline response."},
    )

    assert rolled_back.status_code == 200, rolled_back.text
    assert rolled_back.json()["document"]["status"] == "approved"
    assert rolled_back.json()["document"]["signature_request_id"] is None
    document = await db_session.get(OnboardingDocument, document_id)
    participant = await db_session.get(OnboardingParticipant, document.participant_id)
    request = await db_session.get(SignatureRequest, request_id)
    recipient = await db_session.get(SignatureRecipient, recipient_id)
    assert document.signature_request_id is None
    assert participant.status == "approved"
    assert request.status == "voided"
    assert recipient.status == "declined"
    assert recipient.otp_hash is None
    audit = (
        await db_session.execute(
            select(SignatureAuditLog).where(SignatureAuditLog.request_id == request_id)
        )
    ).scalar_one()
    assert audit.action == "voided"


async def test_delete_case_and_remind_signers(super_admin, db_session, client):
    get_settings().smtp_host = None
    created = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/onboarding/cases",
        json={
            "kind": "volunteer",
            "title": "To be deleted packet",
            "participant": {
                "name": "Delete Me",
                "email": "delete@example.com",
                "date_of_birth": "2005-04-02",
            },
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    # Remind pending signers
    remind_resp = await request_as(
        client,
        super_admin.id,
        "POST",
        f"/api/onboarding/cases/{case_id}/remind",
    )
    assert remind_resp.status_code == 200, remind_resp.text
    assert remind_resp.json()["reminded_count"] == 1
    assert "delete@example.com" in remind_resp.json()["reminded"]

    # Delete case
    delete_resp = await request_as(
        client,
        super_admin.id,
        "DELETE",
        f"/api/onboarding/cases/{case_id}",
    )
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["ok"] is True
    assert "delete@example.com" in delete_resp.json()["notified"]

    # Verify case is gone from DB
    get_resp = await request_as(
        client,
        super_admin.id,
        "GET",
        f"/api/onboarding/cases/{case_id}",
    )
    assert get_resp.status_code == 404

    # Verify audit log recorded
    audit_actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "onboarding.case_deleted" in audit_actions
