# IAM rebuild implementation and rollout

Approved design: `docs/superpowers/specs/2026-10-01-iam-rebuild-design.md`.

## Step 1: Remove seeding

Remove startup seeding, disable the legacy admin rebuild endpoint, and make plugin discovery read-only for configuration. Retire production seed functions; retain declarative capability metadata without writing it on boot. Verify revoked/missing configuration remains absent after discovery and startup.

## Step 2: Repair IAM

Unify single and batch scope decisions, validate policy scopes, expose active effective capabilities and explain-access inspection, add transactional policy editing and fork assignments, and remove implicit first-user/system privilege elevation. Verify scope isolation, expiry, delegation boundaries, and service authentication with regression tests.

## Step 3: Repair provisioning and onboarding

Preserve manual memberships; remove stale sync-owned memberships only after a successful complete guild fetch. Provide fork-scoped onboarding list/create/read and participant management while retaining global review and public portal protections. Verify cross-fork denial and author/reviewer separation.

## Step 4: Repair frontend

Use active capabilities for navigation and requests. Keep successful overview sections visible with explicit restricted/unavailable states. Rebuild IAM administration around group policies, memberships, fork assignments, and effective access. Remove seed-driven admin controls and copy. Verify web tests, typecheck, and production build.

## Step 5: Review and rollout

Run API checks and meaningful suites, review authorization paths and final diff, and commit atomic changes. Privately back up current production IAM tables and deployment revision. Prepare and apply the approved exact role/assignment diff with audit evidence. Push through the existing health-gated CI deployment, verify backend and web revisions, test affected users with signed internal requests, and confirm cross-fork denials. Roll back code/policy independently using the saved evidence if verification fails; never reset the database or replay seeds.
