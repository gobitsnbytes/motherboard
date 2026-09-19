# Semantic OOXML Onboarding Editor

**Date:** 2026-09-19  
**Status:** Approved architecture; implementation pending  
**Scope:** Onboarding Forms 1–5 in `templates/`. Form 6 (minor event consent) is explicitly excluded.

## 1. Outcome

Replace the current evidence-append onboarding flow with a browser document editor backed by genuine OOXML round-tripping. Participants fill the original legal templates in place, add their electronic signatures, and submit them for HQ review. The final PDF is generated only after the required HQ signers countersign. The completed artifact includes a cryptographic seal, an append-only audit trail, and a verification certificate.

The authoritative pre-finalization artifact is a versioned OOXML package plus typed field state. A PDF is a final output, not the draft source of truth.

## 2. Included templates

1. `1_Volunteer_Form.docx` — Volunteer & Engagement Form
2. `2_Parents_Consent_.docx` — Parent/Guardian Consent Form
3. `3_Fork_Recognition_Certificate.docx` — Fork Recognition Certificate
4. `4_Fork_Agreement.docx` — Fork Recognition Agreement
5. `5_Fork_Application_Form.docx` — Fork Onboarding Form

`6_Minor_Consent_Event.docx` belongs to a later event-participant workflow and must not be registered in the onboarding editor.

## 3. Existing-template findings

The templates are valid DOCX/OOXML packages, but they are not semantically fillable:

- Existing structured document tags use generic Google-export tags such as `goog_rdk_0`.
- The tags wrap ordinary prose, separators, and checkbox glyphs rather than named form fields.
- Most input locations are represented by tabs, empty runs, or underscore characters.
- Template layout includes paragraphs, drawings, and—in Forms 3–5—tables.
- There are no useful bookmarks or stable field identifiers.

The compiler therefore requires a one-time annotation stage. It must not infer fields from surrounding text during normal document execution.

## 4. Design principles

- **Deterministic legal output:** Compilation uses explicit field anchors, never semantic search or model inference.
- **Immutable template versions:** A published template package is never edited in place.
- **Typed state:** Dates, booleans, choices, addresses, signatures, and text are represented explicitly.
- **XML-backed drafts:** Every accepted draft revision has a materialized OOXML snapshot and matching normalized field state.
- **Fail closed:** Unknown template versions, missing required fields, stale revisions, invalid signatures, or hash mismatches stop progression.
- **No final PDF before countersignature:** Preview rendering may be used internally, but no completed PDF is issued before all required signatures are present.
- **Append-only evidence:** Audit and signature records are never rewritten to hide prior events.
- **Separation of concerns:** Template analysis, draft editing, signing, compilation, and verification are independent modules.

## 5. Template annotation and registry

### 5.1 Annotation command

A local, deterministic template-import command will:

1. Open the DOCX as a ZIP package.
2. Validate required OOXML parts and reject unsafe or unsupported relationships.
3. Extract package parts into a versioned template directory.
4. Record the original package SHA-256 hash.
5. Apply the reviewed field map for that exact template hash.
6. Replace each mapped blank with a semantic content control or bookmark.
7. Save an annotated OOXML package and field registry.
8. Repackage and render a fixture to verify that layout remains intact.

The import process is an administrative build step. Runtime document creation only uses previously published template versions.

### 5.2 Semantic identifiers

Field identifiers are stable and namespaced:

```text
bnb.volunteer.full_name
bnb.volunteer.date_of_birth
bnb.parent.guardian_name
bnb.fork.application.fork_name
bnb.fork.agreement.effective_date
bnb.fork.certificate.director_one_signature
```

Each field definition contains:

- `id`
- `label`
- `type`
- `required`
- `document_part`
- `anchor_kind`
- `anchor_id`
- `section`
- `help_text`
- `validation`
- `visibility_rule`
- `editable_by`
- `signer_role`
- `display_order`

### 5.3 Supported field types

- short text
- multiline text
- email
- phone
- date
- number
- single choice
- multiple choice
- checkbox/affirmation
- address group
- computed value
- initials
- electronic signature
- HQ seal/signature

Computed values such as age, certificate reference, and signing date are generated server-side and are not trusted from browser input.

## 6. Persistence model

### 6.1 Template version

`DocumentTemplateVersion` records:

- logical template key
- version number
- original filename
- original package hash
- annotated package hash
- storage path
- field registry JSON
- signer policy JSON
- status: `draft`, `published`, `retired`
- creation and publication metadata

Only published versions may create document instances.

### 6.2 Document instance

`OnboardingDocument` is extended with:

- `template_version_id`
- `draft_status`
- `current_revision`
- `current_state_hash`
- `xml_package_path`
- `final_docx_path`
- `final_pdf_path`
- `final_docx_hash`
- `final_pdf_hash`
- `finalized_at`

Its existing onboarding-case and signature-request relationships remain intact.

### 6.3 Revisions

`DocumentDraftRevision` records:

- document ID
- monotonically increasing revision number
- canonical field-state JSON
- materialized XML package path
- package hash
- previous revision hash
- revision hash
- actor type and actor ID
- creation timestamp

The canonical revision hash covers the document ID, template version, revision number, previous hash, normalized state, package hash, and timestamp.

### 6.4 Audit events

Document editing events are stored separately from signature events but linked to the same document and eventual signature request. Events include:

- draft opened
- field changed (field ID and before/after hashes, not sensitive plaintext)
- autosave accepted
- stale save rejected
- participant submitted
- participant signature requested/completed
- HQ review opened
- HQ rejected or returned for correction
- HQ signature requested/completed
- document frozen
- DOCX compiled
- PDF rendered
- cryptographic seal created
- certificate generated
- public verification performed

## 7. OOXML draft contract

Each document instance receives a private copy of the published annotated package. The package is stored unpacked under a document/revision-specific directory.

Draft saves carry:

```json
{
  "base_revision": 7,
  "changes": [
    {"field_id": "bnb.volunteer.full_name", "value": "Example Name"}
  ]
}
```

The server:

1. Authorizes the token or IAM principal for every changed field.
2. Validates field types and business rules.
3. Rejects a stale `base_revision` with HTTP 409.
4. Applies changes to normalized state.
5. Writes values into a fresh copy of the previous OOXML package.
6. Canonicalizes and hashes the new package and state.
7. Persists the revision and audit event transactionally.

The browser never uploads arbitrary XML and cannot select filesystem paths or package relationships.

## 8. Browser editor

### 8.1 Page structure

The editor route remains token-scoped for participants and authenticated for HQ staff. The primary layout contains:

- document title, template version, and save status
- section navigator with completion indicators
- paginated document canvas preserving the original section order
- inline field controls embedded at semantic anchors
- signer panel with role chips and signature status
- validation summary
- review-and-submit action

Mobile uses a single-column document flow with a collapsible section navigator. Desktop uses a document canvas plus sticky progress/signing rail.

### 8.2 Rendering contract

The frontend receives a safe document view model, not raw OOXML. The view model contains semantic blocks:

```text
page → section → paragraph/table → text runs and field nodes
```

Supported layout elements are paragraphs, headings, lists, tables, separators, images, page breaks, and inline fields. Unsupported constructs are rendered as read-only fallback blocks and recorded during template publication.

The compiler remains authoritative. Browser rendering is an editing projection, not an independent document source.

### 8.3 Signature chips

Signature fields render as role-aware chips:

- `Signature required`
- `Ready to sign`
- `Signed by participant`
- `Waiting for HQ`
- `Signed by HQ`
- `Invalidated by revision`

Selecting a ready participant chip opens the existing signing experience. HQ chips are inaccessible to portal-token users. A signature references the exact revision hash it approved.

### 8.4 Autosave

- Debounced saves occur after editing pauses.
- Navigation and submission force a save.
- Visible states are `Saving`, `Saved`, `Offline changes`, and `Conflict`.
- A conflict reloads the current revision and displays which fields changed; it never silently merges signatures or legal affirmations.

## 9. Authorization and signer policy

Participant access uses the existing hashed, expiring portal token scoped to one participant. Staff actions use existing IAM principals.

Required permissions:

- `onboarding.read`
- `onboarding.write`
- `onboarding.review`
- `onboarding.certificate`
- a dedicated HQ signing permission, `onboarding.sign_hq`

Template field definitions declare who may edit each field. Participant users cannot edit HQ-only findings, approval decisions, certificate references, or HQ signatures.

Case creators remain prohibited from approving their own cases. Signer policy may require multiple distinct HQ signers for the recognition certificate. Identity, signer order, and signature method are enforced server-side.

## 10. Signing lifecycle

Document status transitions are explicit:

```text
draft
  → participant_submitted
  → participant_signing
  → participant_signed
  → hq_review
  → hq_signing
  → hq_signed
  → compiling
  → completed
```

Exceptional states are `returned_for_correction`, `rejected`, `voided`, and `compilation_failed`.

Rules:

- Submission freezes participant-editable fields for that revision.
- Returning a document creates a new draft revision and invalidates signatures bound to the prior revision.
- Every signature stores the signed revision hash.
- Compilation starts only when every required signer has completed in policy order.
- Retrying a failed compilation is idempotent and does not create duplicate completed artifacts.

## 11. Final compilation and cryptographic evidence

After the final HQ signature:

1. Lock the document instance for finalization.
2. Revalidate required fields, signer identities, signer order, and revision hashes.
3. Copy the frozen unpacked package to an isolated compilation directory.
4. Inject final field values and signature appearances into semantic anchors.
5. Update package metadata and OOXML relationships deterministically.
6. Repackage the directory as a valid DOCX.
7. Validate that the DOCX reopens and contains expected anchors/values.
8. Render the DOCX to PDF using headless LibreOffice.
9. Apply the existing signature engine’s visible signatures and cryptographic evidence.
10. Generate the audit-certificate page with template hash, revision hash, DOCX hash, PDF hash, signers, timestamps, and audit events.
11. Append the certificate to the PDF and calculate the final sealed PDF hash.
12. Persist immutable artifact metadata and mark the document `completed`.

The final DOCX and PDF are both retained. Public verification uses the final hash and returns the template version, completion state, signer summary, and public-safe audit trail.

## 12. Search and storage boundary

Qenlo and other vector databases are excluded from this subsystem. Template filling, revision state, compilation, signing, and verification require exact identifiers and deterministic database lookups rather than semantic retrieval.

The implementation uses PostgreSQL for structured state, private filesystem or object storage for OOXML/artifacts, and cryptographic hashes for integrity. No vector index is installed, queried, or placed on the document execution path.

## 13. API surface

Planned endpoints:

```text
GET    /api/onboarding/public/{token}/documents/{document_id}/editor
PATCH  /api/onboarding/public/{token}/documents/{document_id}/draft
POST   /api/onboarding/public/{token}/documents/{document_id}/submit
POST   /api/onboarding/public/{token}/documents/{document_id}/sign

GET    /api/onboarding/cases/{case_id}/documents/{document_id}/editor
POST   /api/onboarding/cases/{case_id}/documents/{document_id}/return
POST   /api/onboarding/cases/{case_id}/documents/{document_id}/hq-sign
GET    /api/onboarding/cases/{case_id}/documents/{document_id}/audit

POST   /api/onboarding/templates/import
POST   /api/onboarding/templates/{template_version_id}/publish
```

Template import may initially remain a CLI-only operation to reduce production attack surface. Runtime public routes never accept DOCX uploads.

## 14. Migration from the current flow

- Existing completed or already-signing documents remain on the legacy evidence-append path and are never rewritten.
- New cases use semantic template versions after all five versions are published and validated.
- Untouched legacy documents may be recreated against the new template version only through an explicit staff action with an audit event.
- The current `TEMPLATE_MANIFEST` is replaced by persisted, versioned registries after migration.
- The current portal URL and case dashboard remain stable while their document components are upgraded.

## 15. Error handling

- Invalid/expired participant token: 404 with no existence disclosure.
- Unauthorized field edit: 403 and audit event.
- Validation error: 422 with field-level messages.
- Stale revision: 409 with current revision and changed field IDs.
- Template/package hash mismatch: halt and mark operator attention required.
- Unsupported OOXML at publication: reject publication with exact part and element details.
- LibreOffice failure: preserve frozen state, mark `compilation_failed`, allow idempotent staff retry.
- Signature/hash mismatch: fail closed, mark signature invalid, require a new signing cycle.

## 16. Testing and acceptance criteria

### 16.1 Template fixtures

Each of Forms 1–5 has:

- a reviewed field inventory
- an annotated template fixture
- expected XML anchors
- representative valid state
- compiled DOCX golden checks
- rendered PDF page-count and text checks

### 16.2 Backend tests

- template package validation and zip-slip rejection
- semantic anchor lookup and replacement
- type and role validation
- optimistic revision conflict handling
- XML/state hash-chain integrity
- participant/HQ authorization boundaries
- signature invalidation after revision
- signer-order enforcement
- compilation idempotency
- final DOCX reopening
- final PDF/audit certificate generation
- public verification

### 16.3 Frontend tests

- all supported field controls
- keyboard-only editing and signing navigation
- autosave states and conflict recovery
- section completion calculation
- mobile and desktop layouts
- participant/HQ field visibility
- signature-chip state transitions
- errors without data loss

### 16.4 End-to-end acceptance

For every included template, a test case must prove:

1. The participant can fill every assigned field in-browser.
2. Saved values exist at the correct semantic anchors in OOXML.
3. The participant can submit and sign the frozen revision.
4. HQ can review and countersign using a distinct authorized principal.
5. No completed PDF exists before the final required HQ signature.
6. The produced DOCX opens successfully and retains template layout.
7. The final PDF contains populated values, signature appearances, and certificate.
8. Public verification validates the final hash and public audit trail.

## 17. Delivery slices

1. OOXML inspection, safe package utilities, and complete field inventories.
2. Template annotation and publication pipeline for Forms 1–5.
3. Persistence migration, revisions, hash chain, and draft APIs.
4. Browser document renderer/editor and autosave.
5. Participant submission and revision-bound signature chips.
6. HQ review, return, approval, and countersigning.
7. Final DOCX/PDF compiler, sealing, certificate, and verification.
8. Migration controls, full regression suite, security review, and production rollout.

## 18. Explicit non-goals

- General-purpose Microsoft Word editing.
- Arbitrary user-uploaded templates.
- Real-time multi-user co-editing.
- AI-generated legal values or inferred signatures.
- Vector search or a vector-database dependency.
- Form 6 event consent in this delivery.
