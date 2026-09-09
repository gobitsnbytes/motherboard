# Motherboard production completion plan

## Step 1 - Contain authorization and false-assurance failures

Lock sensitive signature, Contract Assistant, plugin, finance, meeting, and fork routes behind explicit owner/IAM policies. Remove or qualify false DSC, immutable, legally binding, and compliance claims. Add negative security tests.

Acceptance: anonymous and read-only principals cannot mutate protected resources; public token routes expose only their scoped task; security tests cover every route family.

## Step 2 - Establish additive schemas and compatibility fixtures

Add outbox/webhook, consent/delivery, signature assurance/evidence chain, finance journal/reconciliation, and plugin artifact state through expand-only migrations. Capture production-shaped legacy signature fixtures.

Acceptance: upgrade/downgrade or forward-fix validation passes; existing signature list/detail/status/download/audit/verify contracts pass unchanged; no historical hash is modified.

## Step 3 - Make calendar and meeting delivery exactly-once

Move all shared scheduling to PostgreSQL, enforce Cal.com uniqueness, replace mirror sync with durable bot claims, secure public booking, and unify transcript/action-item/delivery ownership.

Acceptance: one staged booking completes the entire lifecycle exactly once, including reschedule and cancellation.

## Step 4 - Complete fork onboarding and evidence-backed compliance

Replace boolean/default-pass checks with evidence adapters, verification state, remediation, guardian consent, and awaited atomic audits.

Acceptance: missing evidence fails closed; every approval transition has authority, evidence, actor, timestamp, and reason.

## Step 5 - Complete the versioned signature service

Harden OTP and signing rules, fix organization countersign completion, build append-only evidence chains and BSA certificates, preserve legacy verification, and implement a vendor-neutral CCA eSign adapter.

Acceptance: low-risk electronic acceptance and CCA eSign are never conflated; legacy records remain usable; provider sandbox callbacks verify identity, certificate status, document hash, and idempotency.

## Step 6 - Complete finance in sandbox and reconcile history

Implement balanced journals, approvals, payees, payouts, webhooks, reconciliation, reversals, periods, and evidence-backed reporting. Quarantine legacy balances.

Acceptance: sandbox payout lifecycle is exactly-once; trial balance ties; invalid/duplicate webhooks fail safely; live mode cannot enable without full preflight.

## Step 7 - Replace dummy plugin state with verified artifacts

Fix per-route permission declarations, artifact allowlisting/digests, registry reconciliation, lifecycle state, and backend/UI version checks. Remove stale registry presentation without deleting evidence.

Acceptance: read users receive 403 on destructive routes; missing or unknown artifacts never import and render a degraded state.

## Step 8 - Unify Motherboard and public booking UI

Apply the approved bits&bytes™ neobrutalist system through shared tokens and primitives. Rework information hierarchy, forms, tables, responsive behavior, accessible states, and truthful copy across operational surfaces and `gobitsnbytes.org/about`.

Acceptance: WCAG 2.2 AA checks, 375/768/1024/1440 layouts, keyboard workflows, reduced motion, no fabricated data, and successful public booking E2E.

## Step 9 - Review, cleanup, and deployment preflight

Run code review, security review, vibe audit/cleanup, dependency scans, full tests/build, migration rehearsals, backups, and a production rollout/rollback plan.

Acceptance: zero P0/P1 findings, clean typecheck/build/tests, verified backups, and documented go/no-go signals.

## Step 10 - Stage, deploy, and verify

Deploy additive migrations and compatibility code, run shadow verification, enable internal canary users, then public flows. Keep live payouts and CCA eSign disabled until their external preflights pass.

Acceptance: health and business signals remain stable; live smoke tests pass; rollback is executable; MEMORY.md and runbooks reflect demonstrated state only.
