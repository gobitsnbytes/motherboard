# IAM rebuild without seeds

Status: approved by the user on 2026-10-01; implementation in progress.

## Problem and evidence

The 2026-10-01 production audit found 72 permission definitions and seven grants. Five grants are the onboarding baseline inserted by the seeder; two are explicit meeting grants for the API service identity. Devaansh and Angel have leadership/HQ memberships but lack operational read grants. Their overview requests receive 403s. `OverviewContent.loadDashboard` uses one `Promise.all`, so a denied audit/forks request prevents successful results from reaching the page and leaves default zero cards.

`main._initialize_application_services` calls `run_seeds` on every startup. `/api/admin/rebuild-permissions` calls the same seeder. `PluginLoader` inserts or updates plugin and permission records on startup. Deleted baseline grants can therefore reappear. The user has explicitly requested that seeding stop.

Shourya's current configured Discord guild membership contains only Builder. Motherboard records Contributor, with no Fork Lead membership, Nagpur fork assignment, or matching onboarding case. The last recorded full guild sync was September 22. IAM cannot infer an assignment from a person's name.

## Recommended approach

Keep the existing users, groups, memberships, grants, and role mappings. Rebuild their administration and evaluation around explicit database policy and resource scope. Application code declares the capabilities its routes need, but does not populate database configuration on boot.

Alternatives considered:

- Hardcoded role-to-permission rules avoid missing grant rows but turn deploys into implicit policy changes and make revocation ineffective. Reject this approach.
- A separate authorization service adds another deployment and policy migration. It does not resolve the current membership, provisioning, and dashboard defects. Defer it.

## Stop seeding

- Remove runtime calls and imports of the system seeder, including startup and the admin rebuild action. Remove the corresponding UI action and setup/deployment instructions that invoke it.
- Startup must not insert or restore groups, grants, role mappings, forks, financial accounts, knowledge-rule files, or plugin permission configuration. Audit plugin load hooks for equivalent writes.
- Plugin discovery may declare route/permission metadata in memory. Loading an existing enabled plugin must not rewrite its persisted configuration; unknown plugins need explicit installation rather than automatic registration.
- Retire seed entry points from supported production workflows. Isolated tests can construct synthetic fixtures directly. Do not introduce a flag that silently re-enables defaults.
- Preserve existing rows and knowledge files. Do not delete data because its historical origin was a seed. Applied migration history stays intact; future IAM schema migrations must not insert default policies.

## Authoritative access model

- Database grants are the source of permission decisions. Discord maps verified role IDs to configured group memberships; a display name or group slug never grants access by itself.
- Manual memberships and fork assignments remain explicit and audited. Sync owns only `discord_sync` memberships and must not revoke manual assignments.
- One evaluator handles both single and batch checks. An unscoped request requires an unexpired global grant. A scoped grant must never satisfy an unscoped request. Batch evaluation currently violates this contract and must be corrected.
- Normalize and validate resource scopes. Use existing `fork:<slug>` conventions against real active forks. Reject unknown principals, permissions, forks, and expired assignments when policies are edited.
- `/api/iam/me` returns active effective capabilities, scope, and the membership/grant that explains each decision. Expired grants are not advertised as current access. Users may inspect their own access without IAM-administration permissions.
- Keep the explicit break-glass `User.is_super_admin` mechanism restricted. Do not promote the first OAuth login or select an arbitrary super-admin to represent the bot/system. Service identities keep individually configured permissions.

## Proposed role policy for explicit review

This matrix describes the intended repair. It is not a seed table or a policy applied automatically at startup. Prepare an exact production diff against existing group IDs and assignments before applying it through audited administration.

| Principal | Intended access | Boundary |
| --- | --- | --- |
| HQ and Executive Leadership | Operational reads for members, forks, plugins, meetings, and audit; existing onboarding author/reviewer separation preserved | Global operations; no automatic finance or IAM mutation privileges |
| Department Leads | Operational reads and onboarding review as required by the documented reviewer workflow | No finance powers or automatic global administration; creators cannot review their own case |
| Fork Leads | Manage team onboarding and fork operations for an explicitly assigned fork | No other forks, global user administration, finance, or IAM mutation |
| Contributors and ordinary members | Own profile, own work, and permitted onboarding/signing flows | No global audit or privileged operational lists |
| API/bot service identities | Individually configured integration capabilities | No human role inheritance or super-admin fallback |

Finance approvals, certificate issuance, signing evidence, and self-review restrictions retain their existing checks. The repair does not grant every defined permission to leadership groups.

## Fork onboarding and provisioning

- Make the signed-in onboarding surface distinguish global HQ administration from management of a lead's assigned fork. Check scope at each operation and filter lists before returning records.
- Preserve public onboarding token boundaries. A lead may invite teammates through their own portal only after submitting the lead packet. Do not replace this with global `onboarding.write`.
- Show missing role mapping, missing fork assignment, and missing lead packet as distinct actionable states.
- For Shourya, prepare an explicit Nagpur fork/lead assignment and onboarding workflow using his verified existing identity. Do not create placeholder users or automatically change Discord roles.
- Review synchronization scheduling and expose freshness/failures. Fetch failures must not clear memberships. Handle removal of guild members and expired memberships without converting manual memberships into sync-owned ones.

## Administration and frontend

- Rework IAM into editable group policies, memberships, verified Discord mappings, and fork assignments. Include effective-access inspection for a selected person with a clear explanation of allowed and denied actions.
- Policy edits validate every target, preserve delegation limits, commit the audit event and change atomically, and provide a before/after preview. Mutation rights do not permit granting powers the actor does not hold or removing out-of-scope grants.
- Use server-computed capabilities to gate sidebar entries, buttons, and data requests. Backend checks remain authoritative.
- Load overview sections independently. A denied section shows restricted access; an unavailable section shows a retry state. Authorized data remains visible. Unknown counts display an unavailable marker rather than zero. Clear old notices after successful retry.
- Apply the same capability contract to plugin panels and IAM pages, avoiding one restricted catalog request hiding the user's own access.

## Verification and rollout

1. Capture a read-only baseline of production IAM configuration and the active deployment revision. Keep rollback material private, outside Git.
2. Remove seeding and prove repeated startup leaves configuration unchanged. A revoked grant must remain absent across startup and plugin discovery.
3. Test single/batch parity, expired grants and memberships, global versus fork scope, cross-fork denial, identity deactivation, delegation limits, and service identities.
4. Test sync ownership and failed-fetch behavior, fork-lead teammate workflows, and onboarding author/reviewer separation.
5. Test partial overview loading and access-aware navigation with synthetic personas matching the observed role shapes. Run API checks, web typecheck/tests/build, and review the final diff.
6. Commit changes in small units. Produce an exact audited production policy and assignment diff; apply only reviewed changes. Deploy through the existing health-gated rollout and verify authorized and denied requests for representative users.
7. A code rollback must not silently replay seeds or undo policy edits. Preserve both deployment and policy rollback evidence. Never reset or replace the database.

## Acceptance criteria

- No supported startup, plugin discovery, deployment, or admin rebuild path runs seed data writes.
- Devaansh and Angel can load authorized overview sections using explicit reviewed grants; unavailable or restricted sections do not erase healthy data.
- A fork lead can onboard their own team and cannot access another fork's onboarding administration.
- IAM shows exactly why a person has or lacks access, and changes persist across restarts.
- Existing real identities, manual assignments, grants, finance records, onboarding documents, and audit history remain intact.

## Implementation order

1. Remove production seeding paths and replace seed-dependent tests with explicit fixtures.
2. Repair policy evaluation, identity boundaries, and effective-access contracts.
3. Add audited, scoped policy/assignment management and correct provisioning ownership.
4. Make IAM, overview, navigation, and onboarding consume the shared capability contract.
5. Review, verify, apply the explicit production repair, and deploy with rollback evidence.
