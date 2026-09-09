# Digital onboarding workflow

**Status:** Proposed
**Date:** 2026-09-09
**Scope:** Volunteer onboarding and fork onboarding

## Purpose

Motherboard needs one workflow for collecting onboarding information, routing the right documents to the right people, reviewing the completed packet, and producing an auditable signed record. The workflow must use the supplied DOCX templates and the existing `bnb-signatures` utility.

The system will support two related journeys:

1. A volunteer completes the Volunteer & Engagement Form. If the person is a minor, a parent or guardian completes a separate consent form from a separate email link.
2. A fork lead completes the volunteer packet, adds teammates only after the lead intake is verified, and then completes the fork application and agreement. Each teammate completes their own volunteer packet and conditional parent consent. After review, two directors sign a prefilled Fork Recognition Certificate.

The signed PDF is the authoritative record. The original DOCX and the filled DOCX are retained as source evidence.

## Decisions

- The first delivery includes both volunteer and fork workflows.
- An onboarding orchestrator owns the workflow. Existing signature requests remain the signing primitive.
- A signed PDF is the canonical legal record.
- The original and filled DOCX files are retained as evidence, each with a SHA-256 hash.
- Participants complete documents in the web portal. The final sealed PDF is static and hash-verifiable.
- Reviewers are assigned per case from IAM-authorized users. Self-approval is rejected.
- External participants use document-scoped links and OTP through the existing signature UI.
- Legal and director signatures happen in the authenticated internal dashboard.
- Legal uses the organizational identity `legal@gobitsnbytes.org`.
- Fork recognition requires two distinct IAM-authorized director signers.
- A fork lead may invite teammates only after the lead intake has been verified.
- A minor under 13 cannot be onboarded. Ages 13 through 17 require parent or guardian consent. Ages 16 and 17 also require the minor to co-sign the consent form.
- Native PDF AcroForm controls are out of scope for the first delivery.

## Current code and constraints

The repository already contains the pieces this workflow should reuse:

- `apps/api/app/routers/signatures.py` handles signature requests, recipient links, OTP, fields, audit logs, countersigning, document download, verification, and voiding.
- `apps/api/app/services/signature_engine.py` overlays values and signatures onto PDFs and appends an audit certificate.
- `apps/web/components/signatures/SigningPortalClient.tsx`, `DocumentEditor.tsx`, and `SignatureCanvas.tsx` provide the participant signing experience and signature methods.
- `apps/api/app/routers/forks.py` contains the existing seven-step operational fork checklist.
- `apps/api/app/routers/meetings.py::send_smtp_email` provides the configured SMTP and Brevo fallback path.
- `apps/api/app/iam/policy.py` and the existing principal resolver provide scoped authorization.

The current DOCX conversion in `signature_engine.py` rebuilds a document from paragraph text. It does not preserve the supplied template layout, tables, or form structure, so onboarding must use a faithful DOCX renderer instead.

The API runtime will provision headless LibreOffice and expose its absolute binary path through the document-rendering configuration. The container will include the Writer component and the fonts needed by the retained templates. Local QA will use the same renderer contract rather than relying on Windows-only Word automation.

The supplied DOCX files contain generic Google-generated `goog_rdk_*` structured-document tags. Those tags do not identify fields. A runtime guesser would be unsafe, so each retained template needs a versioned field manifest based on its raw OOXML and stable text anchors.

## Architecture

The new module sits between the dashboard/public portal and the signature system:

```text
Onboarding case
  -> participants and conditional rules
  -> document packet and template manifests
  -> child signature requests
  -> reviewer decision
  -> internal countersignatures
  -> sealed PDFs, DOCX evidence, and verification data
```

The onboarding module does not copy signing logic. It creates and coordinates child `SignatureRequest` records and uses their recipient, field, audit, OTP, and sealing behavior. It adds the missing relationship between a business onboarding case and several documents.

### Case types

`volunteer` cases contain one subject participant and, when required, one parent or guardian participant.

`fork` cases contain one fork lead, zero or more invited teammates, any required parents or guardians, one assigned reviewer, and two director signers for the recognition certificate. The case references an existing `Fork` row after fork creation or approval, depending on the current lifecycle.

### Case states

The state machine is:

```text
draft -> collecting -> review -> accepted -> countersigning -> completed
                       |          |
                       |          +-> rejected
                       +-> changes_requested -> collecting

draft, collecting, review, changes_requested -> expired or cancelled
```

Transitions are server-side commands, not free-form status updates. Every transition records an immutable audit event. A change request creates a new packet revision and voids active signing links for the affected documents. Prior revisions remain readable to authorized staff.

## Data model

The implementation will use the following table names and relationships.

### `onboarding_cases`

Stores the workflow root.

- `id`
- `kind`: `volunteer` or `fork`
- `status`
- `revision`
- `subject_user_id`, nullable until identity reconciliation completes
- `fork_id`, nullable for volunteer cases
- `created_by`
- `reviewer_user_id`
- `reviewer_scope`
- `case_data_json`: validated workflow data used for prefill and certificate generation
- `created_at`, `updated_at`, `expires_at`, `completed_at`

The case data is not a substitute for participant or document records. It stores the approved snapshot used to generate a packet and certificate.

### `onboarding_participants`

Stores a person involved in the case.

- `id`, `case_id`
- `role`: `volunteer`, `fork_lead`, `parent_guardian`, `teammate`, `reviewer`, `legal`, or `director`
- `name`, `email`
- `relationship`, nullable for non-guardian roles
- `user_id`, nullable for external participants
- `status`: `invited`, `verified`, `submitted`, `approved`, `rejected`, `revoked`
- `invite_token_hash`, `invite_expires_at`, `verified_at`, `revoked_at`
- `metadata_json`

Invite tokens are stored as hashes. A token is scoped to one participant and one case and cannot be used to enumerate other documents.

### `onboarding_documents`

Stores one packet document per revision.

- `id`, `case_id`, `participant_id`
- `template_key`, `manifest_version`
- `document_role`: `volunteer_form`, `parent_consent`, `fork_application`, `fork_agreement`, `recognition_certificate`, or `event_minor_consent`
- `status`: `pending`, `in_progress`, `submitted`, `changes_requested`, `accepted`, `countersigning`, `completed`, `voided`
- `original_docx_path`, `original_docx_hash`
- `filled_docx_path`, `filled_docx_hash`
- `signature_request_id`
- `canonical_pdf_path`, `canonical_pdf_hash`
- `revision`, `submitted_at`, `accepted_at`, `completed_at`

The original file points to the retained template snapshot used for that packet. It is never overwritten by a later template version.

### `onboarding_reviews`

Stores append-only review decisions.

- `id`, `case_id`, `revision`, `reviewer_user_id`
- `decision`: `accepted`, `changes_requested`, or `rejected`
- `reason`, required for changes and rejection
- `created_at`

The latest accepted decision can advance the case, but earlier decisions remain part of the audit history.

### Audit and evidence

Onboarding events use the existing audit infrastructure with case and document references in structured metadata. Signature audit events remain in `signature_audit_logs`. A completed case must be reconstructable from the onboarding records, signature records, hashes, and certificate pages.

## Volunteer workflow

### Initiation

An authorized staff member creates a case with the subject's name, email, date of birth, capacity, optional parent or guardian email, and an assigned reviewer. The API computes age from the date of birth using the current date and does not trust a client-supplied age.

The API rejects dates that would make the subject younger than 13. A minor case cannot enter collection without a parent or guardian email. The parent email is normalized and checked for duplication within the case.

### Packet generation

The system creates a Volunteer & Engagement Form for the subject. It pre-fills identity and capacity fields but keeps participant-entered fields editable until submission.

For ages 13 through 17, it creates a Parental / Guardian Consent Form for the parent or guardian. The minor identity fields are prefilled and read-only in the parent portal. For ages 16 and 17, the document has a second signature recipient for the minor co-signature after the parent signs.

### Completion and review

The subject and parent receive separate email messages containing only their own scoped portal links. Each signer completes required fields and signs through the existing signature utility. When all required child signature requests are complete, the case enters `review`.

The assigned reviewer can inspect the documents and evidence, accept the revision, request changes with a reason, or reject the case. A request for changes creates a new revision and sends only the affected participants new links.

### Countersignature and completion

After acceptance, the legal countersignature action is visible in the internal dashboard. The participant's name and approved data are already embedded in the document fields. The internal signer identity is recorded separately. Once legal signs, the document is sealed and the case becomes `completed` when every required document has a canonical PDF.

## Fork workflow

### Lead intake

Staff creates a fork case with the proposed fork name, type, location, institutional context where applicable, proposed domain, and lead email. The lead receives a scoped intake link.

The lead must complete the volunteer form and conditional parent consent before the teammate-management action becomes available. Lead verification means the lead's email/session is verified and the lead packet has reached `submitted`; it does not mean the fork is approved.

### Teammate invitations

Only the verified lead's scoped portal session can add teammate emails. The server checks that the session belongs to the fork lead participant, the case is still collecting, and the email is not already used in the case. Adding an email creates a participant record and the appropriate volunteer packet. If the teammate is a minor, the teammate supplies a parent or guardian email and receives the same conditional consent flow.

The lead cannot invite a reviewer, legal signer, or director. Those roles are assigned by staff or IAM policy.

### Fork documents

The lead receives a Fork Onboarding Form and Fork Recognition Agreement. The forms are prefilled from the case and the lead's verified volunteer identity. The agreement is not issued until the lead's own volunteer packet is submitted.

The existing seven-step fork checklist remains linked to the case. Checklist completion and document completion are separate signals. Recognition requires the document packet, review acceptance, and the operational checks required by the existing fork lifecycle.

### Recognition certificate

After review acceptance and all required teammate packets are complete, the system generates a Fork Recognition Certificate from the approved case snapshot. It pre-fills the certificate number, fork name, lead name, location, recognition date, agreement reference, and approved team details.

The certificate is sent to two distinct director users selected through IAM. Both sign in the internal dashboard. If either signer declines or loses authorization, the certificate remains pending and the case cannot complete. A signed certificate is sealed as the canonical fork recognition PDF and linked to the `Fork` record.

## Template manifest and document pipeline

The six retained templates are registered as:

| Key | Source file |
|---|---|
| `volunteer_form` | `templates/1_Volunteer_Form.docx` |
| `parent_consent_fork` | `templates/2_Parents_Consent_Fork.docx` |
| `fork_recognition_certificate` | `templates/3_Fork_Recognition_Certificate.docx` |
| `fork_agreement` | `templates/4_Fork_Agreement.docx` |
| `fork_application` | `templates/5_Fork_Application_Form.docx` |
| `minor_consent_event` | `templates/6_Minor_Consent_Event.docx` |

Each manifest version includes:

- Template source hash
- Semantic field key
- Field type and required rule
- Participant role
- Prefill source or editable status
- OOXML target anchor
- Rendered PDF page and percentage placement
- Checkbox value mapping where applicable

The manifest is checked into the repository with the code that consumes it. A template source hash mismatch prevents packet generation until a new manifest version is registered.

The fill pipeline is:

1. Read the registered source DOCX as a ZIP package.
2. Apply validated prefill and submitted values to a copy using targeted OOXML edits.
3. Preserve styles, tables, section breaks, headers, and footers.
4. Render the filled DOCX through the bundled, production-approved DOCX-to-PDF renderer.
5. Create web fields and signatures from the manifest and `SignatureField` records.
6. Seal the PDF with `embed_signatures_and_seal` and store its final hash.

The current paragraph-text rebuild is not used for these packets. The first implementation must resolve the configured LibreOffice path explicitly and fail closed when it is unavailable. The initial read-only renderer check found that `soffice.exe` was not on the workstation PATH, and the current API Dockerfile does not install a DOCX renderer.

The portal is the only interactive completion surface. The final PDF does not retain editable controls. A downloaded source DOCX is evidence, not a second signing surface.

## Authorization model

The new permission keys should follow existing IAM conventions:

- `onboarding.read`
- `onboarding.create`
- `onboarding.write`
- `onboarding.review`
- `onboarding.reassign`
- `onboarding.countersign`
- `onboarding.director_sign`

Permissions are checked globally or against a fork scope. The reviewer must have `onboarding.review` for the case scope. The legal signer must have `onboarding.countersign`. Director signers must have `onboarding.director_sign` and an active director role. The API rejects a reviewer who is also the case subject or an external participant.

The case creator may assign a reviewer only if the creator has the reassignment permission or is assigning an authorized reviewer at creation time. Reassignment records the previous and new reviewer and reason.

## API and UI surfaces

### Staff API

The onboarding router will provide endpoints for:

- Creating and listing cases
- Reading a case with packet and audit status
- Assigning or reassigning a reviewer
- Adding fork teammates after lead verification
- Resending or revoking an invite
- Recording review decisions
- Starting legal countersigning
- Selecting director signers and starting certificate signing
- Downloading evidence and canonical PDFs for authorized staff

### Public portal API

The public surface will provide token-scoped endpoints for:

- Reading the participant's assigned document and required fields
- Saving a draft
- Submitting fields and signatures to the child signature request
- Requesting OTP and verifying OTP
- Reading only the participant's own completion status

The public API must not return the full case, other participants, reviewer identity, internal notes, or unrelated documents.

### Web UI

Add an internal onboarding queue and case detail page under the dashboard. The detail page should show packet status, revision history, reviewer actions, audit events, evidence hashes, and signing actions. Fork detail should show teammate packet progress alongside the existing operational checklist.

Add a public onboarding portal route that reuses the current signing components but receives a preconfigured document packet rather than arbitrary staff-placed fields. The portal should support save-and-return, required-field validation, OTP, signature methods allowed by the recipient, and a clear final-submit action.

## Notifications

Use the existing SMTP/Brevo helper for invitations, change requests, review results, and signing reminders. Messages contain a scoped portal URL and do not attach personal documents. Invite creation and resend operations are idempotent and audited. Email delivery status is recorded separately from document status so a delivery failure does not make the document appear complete.

The existing organization audit-copy behavior is preserved. Sensitive form data stays behind the portal link.

## Security and privacy requirements

- Hash invite tokens at rest and use constant-time comparison.
- Expire and revoke tokens on completion, revision, rejection, or cancellation.
- Require OTP for external signatures and sensitive portal actions.
- Enforce case, participant, document, and fork scope at every endpoint.
- Escape all values inserted into HTML email and PDF text.
- Validate DOCX uploads, paths, file size, and content type at the trust boundary.
- Keep evidence files outside the public web root and serve them through authorization checks.
- Never use client-provided age, role, reviewer, director, or signature metadata as an authority decision.
- Preserve append-only audit records for invitations, views, saves, submissions, review decisions, signatures, resends, revocations, and downloads.
- Keep participant identity fields separate from legal or director signer identity.
- Prevent a parent link from seeing the child's other documents or other case participants.
- Do not silently overwrite a submitted or signed revision.

## Verification plan

Backend tests must cover:

- Template source hash and manifest validation
- Field prefill and filled-DOCX preservation
- Age boundaries at 12/13, 17/18, and the 16+ co-sign rule
- Parent-link isolation and token expiry
- Fork lead-only teammate creation
- Duplicate teammate rejection
- Reviewer assignment and self-approval rejection
- Change-request revisioning and old-link revocation
- Legal countersign authorization
- Two distinct director signers
- Fork checklist and packet gating
- Evidence hashes and final PDF verification
- Email idempotency and resend audit events

Frontend checks must cover:

- Public portal field validation and save-and-return
- Role-specific document visibility
- Signature method restrictions
- Review and signing actions in the dashboard
- Fork teammate progress and certificate status

Document QA must render every template and at least one filled sample for each document role. Each page must be inspected for clipping, table breakage, lost formatting, missing glyphs, incorrect checkbox marks, and signature placement. The final sealed PDF must verify against its stored hash and audit certificate.

## Delivery shape

The implementation remains one product delivery, but it should land in reviewable slices:

1. Template registry, XML manifest reader, faithful renderer, evidence storage, and onboarding tables.
2. Volunteer case creation, conditional parent flow, participant portal, and signature-request orchestration.
3. Fork lead flow, lead-gated teammate invitations, team packet aggregation, and checklist linkage.
4. Reviewer queue, revisioning, internal legal countersignature, director signing, and certificate generation.
5. End-to-end tests, rendered-document QA, security review, and cleanup of redundant signature/template paths.

No generic workflow builder, native AcroForm editor, or new independent signing engine is required for this scope.
