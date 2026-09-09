# Motherboard production completion design

## 1. Executive Summary

### Problem Statement

Motherboard exposes production-looking calendar, signature, finance, compliance, and plugin surfaces while several underlying paths are split across databases, rely on hard-coded assertions, lack authorization, or stop at provider stubs. Existing records and endpoints also have consumers that cannot be broken during repair.

### Proposed Solution

Harden the existing system through additive, versioned migrations. PostgreSQL becomes the sole operational authority; provider operations use verified webhook inboxes and idempotent outboxes; compliance is computed from evidence; public endpoints are least-privilege; and the UI is rebuilt on the existing bits&bytes™ tokens. Legacy signature records remain readable and verifiable through a compatibility layer while new records use an explicit assurance level.

### Success Criteria

- Zero unauthenticated destructive internal endpoints and a tested owner/IAM matrix for every sensitive route.
- One public booking completes booking, invite, call state, recording consent, transcript, action items, delivery, reschedule, and cancellation exactly once.
- Every new financial posting balances debits and credits; RazorpayX sandbox events reconcile exactly once before live mode can be enabled.
- Every new signature states its assurance level and produces a complete, tamper-evident evidence package; regulated eSign is accepted only from a configured CCA-empanelled provider.
- Existing signature URLs, response fields, PDFs, hashes, and verification paths remain available without changing historical evidence.
- No operational seed or fabricated metric appears in production.
- Typecheck, build, unit, integration, security, migration, and staged E2E gates pass before production rollout.

## 2. User Experience & Functionality

### User Personas

- Board/legal operator: prepares agreements, verifies authority, dispatches signatures, countersigns, and exports evidence.
- Finance operator/reviewer: records evidence, prepares payouts, approves within the authority matrix, and reconciles bank events.
- Team host: publishes availability and receives bookings without exposing private schedule data.
- Meeting owner/attendee: manages calls, consent, recordings, transcripts, and assigned work.
- Fork reviewer/lead: completes evidence-backed onboarding and compliance remediation.
- Platform administrator: installs approved plugins, grants permissions, monitors integration health, and deploys safely.
- Public guest/signatory: completes a booking or signature with minimal disclosure and a clear recovery path.

### User Stories and Acceptance Criteria

#### Calendar and calls

As a guest, I can select a real team member and available slot so that a confirmed booking is created once.

- Host identity and event type are resolved server-side from an allowlisted public profile.
- Slot availability is revalidated inside the booking transaction.
- CAPTCHA, rate limits, OTP attempt limits, and idempotency apply to public mutations.
- Cal.com webhook events have unique provider IDs and tolerate duplicates and out-of-order delivery.
- The bot claims durable call jobs from PostgreSQL; it does not mirror meetings into SQLite.
- One component owns transcript and action-item creation; delivery attempts are durable and retryable.

#### Fork onboarding and compliance

As a reviewer, I can see which required evidence exists, who verified it, and what blocks approval.

- Missing evidence fails closed; no statutory or governance check defaults to pass.
- Checklist transitions require evidence adapters, actor authority, timestamps, and reason codes.
- Minor/guardian identity, consent scope, withdrawal, retention, and access are recorded explicitly.
- Every audit write is awaited and committed with the domain transition.

#### Signatures

As an operator, I can dispatch a document under the correct assurance level and preserve a complete evidence trail.

- `electronic_acceptance_v1` supports typed/drawn/uploaded marks for permitted low-risk documents and never calls itself CCA eSign or DSC.
- `cca_esign_v1` is available only through a configured empanelled provider adapter and verified callback.
- OTP challenges are hashed, expiring, attempt-limited, rate-limited, single-use, and bound to the recipient/session/document.
- Signing order, required fields, recipient role, consent, and document hash are enforced server-side.
- Organization countersign remains pending until all required signers finish and cannot be bypassed by ordinary completion.
- Audit events form a hash chain and terminal evidence cannot be cascade-deleted; retention/legal-hold rules replace public purge.
- A BSA Section 63 evidence certificate is generated from stored facts without claiming automatic admissibility.

#### Signature backward compatibility

As a holder of an existing signing link or completed document, I can continue using the historical workflow after the upgrade.

- Existing `/api/signatures/*`, `/sign/{token}`, and `/verify/*` paths keep their documented shapes; new fields are optional/additive.
- Existing access tokens remain resolvable unless already expired, voided, or revoked.
- Existing original and executed files remain downloadable under the same authorization rules after storage migration.
- Historical `document_hash` values are never recomputed or overwritten.
- Historical audit rows are preserved byte-for-byte and exposed as `legacy_evidence_v1`; new chain fields may reference but never rewrite them.
- Completed legacy envelopes remain verifiable as historical electronic-acceptance evidence, not upgraded or relabelled as CCA eSign.
- A compatibility test fixture created from production-shaped legacy rows passes list, detail, sign-status, download, audit, and verify flows.
- API removals or required-field changes require a separate deprecation release; none are allowed in this program.

#### Finance

As a finance operator, I can prepare and reconcile legitimate transactions without fabricating bank truth.

- Journal entries contain balanced immutable lines; corrections use reversals.
- Legacy unexplained balances are quarantined until bank-statement and accountant approval produces opening entries.
- Payouts require payee/fund-account evidence, authority snapshots, distinct approvals, and an idempotency key.
- RazorpayX webhooks are raw-body signature verified, deduplicated, and reconciled with provider transactions.
- Live money movement is disabled until KYC/account, keys, webhook secret, IP allowlist, sandbox E2E, and explicit go-live configuration pass.
- Compliance indicators link to current evidence and state `not assessed`, `not applicable`, `needs review`, or `verified`; they never hard-code pass.

#### Plugins

As an administrator, I can enable a real versioned plugin without granting read users destructive privileges.

- Every route declares its permission; admin actions cannot inherit panel read permissions.
- Only allowlisted artifacts with recorded source, version, and digest are imported.
- Missing or mismatched backend/UI artifacts mark the registry degraded and unavailable.
- Installation and lifecycle state are deterministic and audited; unknown filesystem code fails closed.

#### Interface consistency

As an operator, I can move between domains without learning a new visual language.

- Shared tokens and primitives replace page-local hex values and inconsistent controls.
- Burgundy, orange, white, and neutral-dark remain the identity; generated blue SaaS palettes are rejected.
- Pages use responsive information hierarchy, accessible tables/forms, clear loading/empty/error states, and one primary action.
- Legal and financial claims are rewritten to match proven system state.

### Non-Goals

- Acting as legal counsel, a chartered accountant, a bank, a certifying authority, or a government filing portal.
- Treating a typed/drawn mark as a regulated DSC/eSign.
- Executing real payouts before external onboarding and the live-mode gate are complete.
- Deleting or silently normalizing unexplained production history.
- Replacing Cal.com, the mail server, or RazorpayX with new scheduling, mail, or banking infrastructure.

## 3. AI System Requirements

### Tool Requirements

- Transcription and summarization use the configured provider through a bounded service interface.
- Legal-agent answers cite stored OKF rules or executed-contract sources and distinguish retrieval from legal advice.
- Provider failures create retryable jobs and visible degraded states; no fake fallback output is persisted as successful.

### Evaluation Strategy

- Golden meeting fixtures measure speaker/timestamp preservation, action-item deduplication, assignment accuracy, and delivery completeness.
- Legal-agent tests require source attribution and abstention when evidence is absent.
- Prompt/output logs redact secrets and protected personal data and retain only the approved operational window.

## 4. Technical Specifications

### Architecture Overview

PostgreSQL is the sole system of record. External commands are written transactionally to an outbox. Workers claim jobs with leases and idempotency keys. Provider callbacks enter a verified webhook inbox before domain projection. Redis may coordinate short-lived limits and locks but is never authoritative.

Core modules:

1. Calendar gateway and meeting lifecycle service.
2. Consent, recording, transcription, action-item, and delivery services.
3. Evidence-backed fork compliance engine.
4. Versioned signature assurance service and immutable evidence store.
5. Double-entry finance journal, payout workflow, and reconciliation service.
6. Signed/allowlisted plugin registry and permission-enforced loader.
7. Shared Next.js product shell and public task surfaces.

### Integration Points

- Cal.com API v2 and signed webhooks.
- Postfix/Dovecot/Brevo with a delivery ledger, bounce/failure state, and RFC-compliant ICS updates.
- CCA-empanelled eSign provider through a vendor-neutral adapter.
- RazorpayX sandbox/live adapters, signed webhooks, and provider transaction reconciliation.
- Discord bot through authenticated Motherboard jobs and callbacks.
- Notion only as an imported evidence source, never the sole compliance authority.

### Data and Migration Strategy

- Expand: add assurance/provider/evidence fields, webhook inboxes, outboxes, relational guests, consent, delivery, journal, approval, reconciliation, and plugin artifact tables.
- Backfill: classify legacy signatures without changing their hashes; quarantine unexplained finance balances; group duplicate Cal.com records and select canonical rows without deleting evidence.
- Shadow: dual-read/compare new projections while legacy API serializers remain active.
- Cut over: switch writers to authoritative services after parity and E2E gates.
- Contract: retire legacy writers only in a later release; compatibility readers remain for retained records.
- Every production migration has preflight counts, validation queries, a backup, and a tested rollback or forward-fix plan.

### Security & Privacy

- Default-deny IAM on internal routes; token-scoped public access with constant-time comparisons.
- CSRF protection for cookie-authenticated mutations, strict CORS/CSP, input/file validation, and per-principal/IP rate limits.
- Secrets remain in environment or secret references and are validated without logging values.
- Signature/private-key material is never accepted unless a reviewed provider flow requires it; Motherboard does not retain signer private keys.
- Public host schemas omit email and raw weekly availability.
- Recording and transcription require affirmative, versioned consent and enforce attendee/owner access, retention, and erasure policy.

## 5. Risks & Roadmap

### Phased Rollout

1. P0 containment: route authorization, plugin permissions, OTP bypass, false legal/compliance copy, and fail-open behavior.
2. Data authority: calendar uniqueness/outbox, awaited audits, signature compatibility fixtures, and migration foundations.
3. Complete vertical services: meetings, forks/compliance, signatures/eSign adapter, finance sandbox, and plugin registry.
4. Product UI: shared shell, domain pages, public booking/signing, accessibility, and error recovery.
5. Staged production: backup, expand migrations, shadow verification, canary operators, public smoke tests, and monitored cutover.

### Technical Risks

- Historical data cannot be assumed correct. Preserve and quarantine it instead of rewriting it.
- CCA eSign and RazorpayX completion depends on external commercial/KYC credentials. Code must be production-complete but remain visibly unavailable until preflight passes.
- One small VPS currently has limited memory. Workers need bounded concurrency and backpressure.
- Cross-repository changes in `D:/bitsnbytes` and `D:/email-server` must preserve their dirty user-owned files and be committed independently.
- Calendar, signature, and finance migrations must remain backward compatible during mixed-version rollout.

### Rollback

- Tag the pre-rollout commit and retain database/file backups.
- Deploy backward-compatible code before enabling new writers.
- Disable provider feature flags and workers first on regression.
- Roll back application artifacts while leaving additive schema intact.
- Never roll back by deleting newly recorded financial, signature, consent, or webhook evidence.
