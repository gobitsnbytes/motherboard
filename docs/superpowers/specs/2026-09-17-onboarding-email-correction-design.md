# Onboarding email correction

## Goal

Allow authorized staff to correct an invited main volunteer or fork-lead email from the internal onboarding dashboard before that participant starts their packet.

## Scope

- Add a staff-only `PATCH /api/onboarding/cases/{case_id}/participants/{participant_id}/email` endpoint.
- Permit it only for the primary `participant` role while every document is still `awaiting_completion` and no signature request exists.
- Validate the replacement with `EmailStr`, reject an email already used by another participant in the case, rotate the participant's portal token, and send a new invitation when SMTP is configured.
- Add an inline edit-email form next to eligible participants on `/dashboard/onboarding` for both volunteer and fork cases.

## Safety and failure behavior

- The endpoint requires `onboarding.write`; portal tokens cannot call it.
- Token rotation makes the old portal URL invalid immediately.
- Once submission or signing begins, the UI hides the action and the API returns `409`, preserving the existing signature/audit trail.
- Parent and teammate email corrections are not included.

## Verification

- Router tests cover successful update and token rotation, duplicate-email rejection, and rejection after a document has moved beyond `awaiting_completion`.
- Web build/type validation confirms the inline form compiles.
