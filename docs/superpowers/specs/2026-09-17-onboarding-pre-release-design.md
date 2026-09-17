# Digital onboarding pre-release design

**Status:** Approved architecture; legal wording and authority remain external ship gates  
**Date:** 17 September 2026  
**Scope:** One production-bound release for adult volunteers, minors with guardians, and prospective Forks

## Decision

Replace the current participant-only onboarding implementation with a case and revision workflow. The implementation composes the existing signature engine; it does not add a generic form builder, a new signature engine, or automated identity/relationship verification.

The present dirty implementation is unreviewed input, not a foundation to preserve. It must not ship its fuzzy label replacement, rewritten DOCX paragraphs, fabricated percentage signature positions, generic evidence appendix, or narrowed CI test command.

## Goals

- HQ starts every volunteer or Fork case through an IAM-authorized command.
- A participant completes only their own, role-scoped questions through a short-lived invitation and recipient-bound email OTP.
- Every filled value has one schema key and one exact marker in a registered template version. Missing, duplicate, or unexpected markers fail closed.
- The participant reviews the exact rendered PDF before signing it.
- Guardian review, independent HQ review, and organizational signing are explicit case commands with immutable audit evidence.
- The completed packet can be downloaded only by an authorized user and its canonical PDF hash can be independently verified.

## Explicit non-goals

- Public case creation, self-service Fork applications, Aadhaar, DigiLocker, biometrics, paid KYC, or automated proof of guardianship.
- Legal wording, Board authority, records-retention duration, or recognition decisions inferred by code.
- Native PDF forms, free-form DOCX editing, generic document field placement, and public evidence storage.

## Domain model

`OnboardingCase` remains the aggregate root. Its `kind` is `volunteer` or `fork`; its state is controlled only by service commands. A new current `OnboardingRevision` holds the immutable answer snapshot and template-version snapshot for one issuance attempt. No document or sign request may span revisions.

New additive records:

| Record | Responsibility | Immutable evidence |
| --- | --- | --- |
| `OnboardingTemplateVersion` | Registered approved template, source hash, schema version, marker and signature-anchor contract | DOCX/PDF source hashes, approval metadata |
| `OnboardingRevision` | One participant-answer and packet issuance version | answer snapshot, notice versions, supersession reason |
| `OnboardingGuardianCheck` | Manual HQ review of guardian declaration for a minor | method, outcome, reviewer, timestamp, restricted evidence reference |
| `OnboardingAuthority` | Current Board/HQ-approved organization-signing authority | authority reference, role, active window |
| `OnboardingEvidence` | Immutable artifact manifest for every generated document | DOCX/PDF hashes and private storage keys |

Existing `OnboardingParticipant`, `OnboardingDocument`, and `OnboardingReview` gain a revision reference. Existing rows remain readable; new guarded workflow paths only create revisioned rows.

### State machine

```text
draft -> invitations_sent -> collecting -> rendered -> awaiting_signatures
  -> awaiting_guardian_check? -> awaiting_review -> awaiting_org_signature
  -> sealed -> completed

changes_requested -> superseded revision -> collecting
rejected | revoked -> terminal for that revision
```

`completed` requires every required document to be sealed, all required guardian checks to be accepted, an independent HQ acceptance, and every required organizational signature. A Fork certificate is unavailable until the separate Board-authorized recognition command succeeds.

## Template and document contract

Each of Forms 1-6 is registered through a `TemplateVersion` object, not a module-level list of label fragments. The registry supplies:

- a stable template key, semantic version, source filename, and SHA-256 hash;
- a Pydantic-compatible field schema with owner, type, validation, conditional rule, privacy classification, and maximum renderable length;
- exact OOXML markers in the form `{{field_key}}`, each expected exactly once;
- explicit PDF signature anchors with page, named anchor, recipient role, sequence, and required flag; and
- the pinned renderer version, font set, and blank/representative visual QA baseline identifier.

The materialization service copies the registered DOCX, verifies its source hash and marker cardinality, then replaces only the XML text nodes containing the declared marker. It preserves runs, styles, tables, headers, footers, and page geometry. It never searches prose labels such as "Name" or rewrites a paragraph's `.text` property.

Rendering uses the production-pinned LibreOffice binary and font set. A missing renderer, failed conversion, missing text anchor, unexpected blank page, or signature anchor outside the rendered PDF blocks issuance. The result is a pre-sign PDF, not an appendix. The signature engine receives only the PDF and the verified anchors assigned to each recipient.

Form 2's cleaned candidate must be copied into the registered production template location only after legal review, its source hash is recorded, and a scan confirms no example personal data. No code path silently substitutes it.

## Participants and packet rules

| Case and person | Documents | Required controls |
| --- | --- | --- |
| Adult volunteer | Form 1 | Participant intake, review acknowledgement, subject signature, HQ review |
| Minor 13-15 | Form 1 and Form 2; Form 6 only for an applicable event | Separate guardian invitation, guardian declaration, HQ guardian check |
| Minor 16-17 | Same as 13-15 plus Form 2 minor acknowledgement when specified by the template version | Minor acknowledgement is never contract authority |
| Fork lead | Forms 1, 4, and 5 | HQ-created case, lead-scoped intake, HQ review, authorized Foundation signer |
| Fork teammate | Form 1; Form 2/6 if a minor | Lead cannot create the case; HQ must enable teammate invitation |
| Recognized Fork | Form 3 only after the prospective packet and operational checklist pass | Board-authorized authority record and lead acknowledgement |

Age is calculated from the date of birth in the service layer on every relevant command. Under-13 cases are rejected. Email OTP proves control of a mailbox only; all UI and audit copy must avoid calling it identity or guardianship verification.

## Commands and authorization

No route creates a case with a public token. Internal commands require server-side IAM checks and create both `AuditLog` and onboarding evidence events. Permissions are resource-scoped where a case belongs to a Fork/city.

| Command | Required permission | Invariants |
| --- | --- | --- |
| Create / invite / resend / revoke | `onboarding.create` | Creator selects reviewer; external user cannot start a case |
| Save draft / submit revision | scoped participant token plus OTP session | Token, recipient, revision, and participant must all match |
| Guardian decision | `onboarding.guardian_check` | Reviewer is independent; method and result are required |
| Review decision | `onboarding.review` | Creator, subject, and signer cannot self-approve; change reason required |
| Release organization signing | `onboarding.release` | Authority record must be active and match document type |
| Download / verify | `onboarding.read` or authorized recipient access | Private storage; every download audited |

Invitation and sign tokens are random, stored as hashes, scoped to recipient and revision, expiring, revocable, and rate-limited. OTP codes are hashed, attempt-limited, expiry-bound, and checked by the signing API -- never trusted from a browser flag or historical audit entry.

## Invitee and HQ interfaces

The public portal is one mobile-first sequence:

1. Case context and privacy notice.
2. Shared details followed by only the participant's conditional questions.
3. Review of generated document PDFs and explicit acknowledgement per PDF.
4. Hand-off to the assigned signing request.
5. A receipt with status and non-sensitive next steps.

Questions have visible labels, persistent helper text, server errors adjacent to their field, semantic input modes, and no preselected media consent. A participant never sees another participant's answers, links, or documents.

The HQ dashboard exposes a case checklist rather than a generic document editor: participant/invitation status, document/template version/hash, guardian check, signer sequence, review action, authority selection, and audited downloads. It uses the established product palette and component vocabulary, a keyboard-complete path, 44px controls, visible focus, responsive tables, and text plus color for all status. Motion is limited to short state feedback and honors reduced-motion preferences.

## Review, correction, and sealing

The review UI displays the exact pre-sign or signed PDF, answer snapshot, template version/hash, notices accepted, sign state, and guardian checklist. `changes_requested` requires a reason and creates a new revision of only the affected documents. It revokes old portal and signing tokens before issuing new ones; it never edits artifacts that have been signed.

The final evidence manifest includes the template version/hash, blank source, filled DOCX/hash, pre-sign PDF/hash, signed PDF/hash, canonical final hash, answer and notice snapshots, signer events, guardian/review decisions, and timestamps. Artifact storage is private, outside the public web root. The verification endpoint proves a final file hash; product copy describes typed signatures accurately and makes no DSC claim unless a real DSC was used.

## API surface

Internal routes are command-oriented under `/api/onboarding/cases/{case_id}`:

- `POST /cases` creates a case and planned participant/document requirements.
- `POST /participants/{id}/invite`, `/resend`, and `/revoke` manage only a current revision's invitation.
- `POST /revisions/{id}/draft`, `/submit`, and `/review-acknowledgements` receive validated participant work.
- `POST /guardian-check`, `/review`, `/release-organization-signing`, and `/complete` execute guarded state transitions.
- `GET /packet` and `GET /documents/{id}/download` use explicit authorization and create a download audit record.

Participant routes remain narrowly public, scoped to a hashed invite token and verified OTP session. They cannot list cases, mutate other participants, make review decisions, or select organization signers.

## Migration and rollout

Migrations are additive and include downgrades for the newly introduced tables and nullable foreign keys. Data migration only backfills metadata where unambiguous; existing packets keep their original behavior and are never silently re-rendered.

The feature is behind an onboarding release flag. It remains disabled until the legal template/signatory authority gates and the technical release contract below are satisfied. This release includes all adult, minor, and Fork paths; if minor approval fails, activation -- not implementation -- remains blocked.

## Test and release contract

- Unit: all six schemas; marker cardinality/hash failures; XML special characters; long values; conditional rules; style preservation; exact anchor resolution; and source PII scans.
- API: IAM matrix; case-creation prohibition; DOB boundaries; token isolation; OTP bypass, expiry, and attempt limits; guardian gate; self-approval; revision revocation; signing sequence; authority routing; and authorized download audit.
- Integration: adult, minor/guardian, and Fork lead/teammate packets from invitation to sealed hash-verifiable PDFs; recomputed hashes; and a failed verification for a tampered PDF.
- Visual: blank and representative filled/signed output for every template, inspected page by page with recorded screenshots and pass/fail checklist.
- Web: keyboard-only invitee and HQ walks; labels and validation announcements; responsive behavior; focus visibility; and WCAG 2.2 AA checks.
- CI: full relevant API and web suites. A focused onboarding-only command is supplemental evidence, never a replacement for the production test suite.

## Delivery slices

1. Remove unsafe document generation and restore full CI coverage.
2. Add revision/template/guardian/authority/evidence schema and migrations.
3. Implement strict DOCX/PDF materialization and template registration.
4. Implement guarded case commands and signature hand-off hardening.
5. Implement invitee and HQ workflow surfaces.
6. Complete end-to-end, visual, accessibility, security, and release-gate QA.
