from sqlalchemy import select

from app.config import get_settings
from app.db.models import (
    AuditLog,
    DiscordAccount,
    Grant,
    OnboardingCase,
    OnboardingDocument,
    OnboardingParticipant,
    User,
)
from conftest import request_as


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
    db_session.add(reviewer)
    await db_session.flush()
    db_session.add(
        Grant(
            principal_type="user",
            principal_id=reviewer.id,
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
    assert self_assignment.status_code == 422
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
    blocked = await request_as(
        client,
        super_admin.id,
        "POST",
        f"/api/onboarding/cases/{case_id}/review",
        json={"decision": "changes_requested", "note": "Creator must not review."},
    )
    assert blocked.status_code == 403


async def test_reviewer_list_requires_explicit_grant_and_deduplicates_identity(
    super_admin, db_session, client
):
    legacy_admin = User(
        display_name="Legacy Admin",
        email="legacy@example.com",
        is_super_admin=True,
    )
    yash_org = User(display_name="Yash Singh", email="yash@gobitsnbytes.org")
    clushed = User(display_name="Clushed✦", email="yashsinghv2770@gmail.com")
    akshat_org = User(display_name="Akshat Kushwaha", email="akshat@gobitsnbytes.org")
    aero = User(display_name="Aero", email="akshatsingh14372@outlook.com")
    db_session.add_all([legacy_admin, yash_org, clushed, akshat_org, aero])
    await db_session.flush()
    db_session.add_all(
        [
            Grant(
                principal_type="user",
                principal_id=yash_org.id,
                permission_key="onboarding.review",
            ),
            Grant(
                principal_type="user",
                principal_id=clushed.id,
                permission_key="onboarding.review",
            ),
            Grant(
                principal_type="user",
                principal_id=akshat_org.id,
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
            ),
            DiscordAccount(
                user_id=aero.id,
                discord_id="223456789012345678",
                username="a3rodev",
            ),
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
            "display_name": "Akshat Kushwaha",
            "email": "akshat@gobitsnbytes.org",
        },
        {
            "id": str(clushed.id),
            "display_name": "Yash Singh",
            "email": "yash@gobitsnbytes.org",
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
