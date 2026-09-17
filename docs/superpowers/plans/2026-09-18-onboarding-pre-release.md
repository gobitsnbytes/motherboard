# Onboarding pre-release implementation plan

**Design:** `docs/superpowers/specs/2026-09-17-onboarding-pre-release-design.md`  
**Target:** `prod` worktree only

## 1. Remove unsafe behavior and establish regression tests

- Restore `.github/workflows/deploy-api.yml` to run the full API suite.
- Replace fuzzy `source_anchor` schema entries, paragraph rewriting, evidence-page generation, and percentage-based signature placement in `apps/api/app/services/onboarding_documents.py`.
- Add failing unit tests for exact marker cardinality, source hash mismatch, XML escaping, and PDF anchors before changing the renderer.

## 2. Add the revisioned persistence contract

- Extend `apps/api/app/db/models.py` with additive template-version, revision, guardian-check, authority, and evidence records plus revision links on current onboarding rows.
- Create an Alembic migration with a reversible downgrade and no destructive data move.
- Extend `apps/api/app/schemas/onboarding.py` with command-specific request/response objects instead of accepting unconstrained answer maps.

## 3. Implement strict materialization and evidence

- Build a registered six-template manifest in `apps/api/app/services/onboarding_documents.py` using explicit field schemas, exact OOXML markers, source hashes, recipient roles, and PDF anchors.
- Verify a copied source's hash and every marker count before replacing text nodes without rewriting DOCX runs or layout.
- Render with the configured pinned renderer, verify anchor text/page location, write private artifacts, and store each artifact hash in the evidence manifest.
- Hand verified anchors to the existing signature engine; never create generic fields for non-signature intake answers.

## 4. Implement guarded workflow commands

- Refactor `apps/api/app/routers/onboarding.py` into service-backed commands for case create, invite lifecycle, draft/submit, review acknowledgement, guardian decision, independent review, organization-signing release, completion, download, and hash verification.
- Enforce IAM in every internal handler, recipient/revision/OTP checks in every participant/signing handler, and audit writes for every state transition.
- Revoke stale portal and signing routes on correction; preserve old artifacts as evidence.

## 5. Build the portal and HQ case checklist

- Replace the current raw portal form with a role-scoped, mobile-first sequence in `apps/web/components/onboarding/OnboardingPortalClient.tsx`.
- Add case-management/checklist views below `apps/web/app/dashboard/onboarding` with explicit guardian, review, authority, and download states.
- Keep signing inside the existing signature surface; the onboarding UI only performs a verified hand-off.

## 6. Verify the release contract

- Add unit, API, integration, accessibility, and full-suite CI coverage for adult, minor/guardian, and Fork flows.
- Render blank and representative packets for all six templates using the production renderer and record page-level screenshots/checklists.
- Run migration upgrade/downgrade, focused/full backend suites, web typecheck/build, and an independent hash-tampering test.

## Commit boundaries

1. `fix(onboarding): restore full CI and reject unsafe document generation`
2. `feat(onboarding): add revision and evidence persistence`
3. `feat(onboarding): materialize registered template versions`
4. `feat(onboarding): enforce guarded case workflow`
5. `feat(onboarding): add case checklist and review portal`
6. `test(onboarding): prove pre-release release gates`
