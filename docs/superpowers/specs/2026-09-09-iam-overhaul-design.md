# IAM Overhaul Design

Date: 2026-09-09
Status: Proposed for review
Scope: Identity and access management for 100 people across 30 city forks

## Problem

Motherboard's IAM is split across two group APIs and currently mixes Discord-derived groups, manual memberships, direct grants, resource scopes, and a break-glass super-admin flag without one enforced contract. The current happy-path tests pass, but the production model has unsafe edges: expired memberships remain active, a generic API key resolves to the first super-admin, mutation payloads are under-validated, `batch_can` has ambiguous scope semantics, and several state changes are not audited.

## Goals

- Make every protected request resolve an accurate, current principal.
- Enforce explicit city/fork and track scopes without accidental cross-city access.
- Make IAM mutations safe, validated, transactional, and auditable.
- Preserve Discord as an upstream identity/group signal without allowing sync to erase manual intent.
- Give operators a usable, legible IAM console that explains effective access and failure reasons.
- Keep the design small enough to operate reliably at roughly 100 users and 30 cities.

## Non-goals

- Replacing Discord OAuth as the user identity provider.
- Building a general-purpose policy language or external authorization service.
- Introducing a new runtime dependency when SQL constraints, Pydantic validation, or existing framework features solve the problem.
- Reworking unrelated finance, meetings, or plugin behavior until they consume the corrected IAM contract.

## Authorization model

### Principal

`ResolvedPrincipal` is computed per request from the database and contains:

- the active user ID;
- non-expired memberships only;
- global role/group identities;
- explicit city/fork and optional track scopes;
- break-glass status, which is an explicit user property and is never inferred from a generic service credential.

Inactive users and expired memberships cannot authorize requests. Membership expiration is evaluated against UTC at resolution time.

### Permissions and grants

Permissions are registered records. A grant must reference an existing permission and a valid user or group principal. `principal_type` is an enum-like constrained value (`user` or `group`) at the schema and database boundary.

Resource scope is explicit:

- `NULL` means global only for permissions marked as global-capable and only when the caller has that global grant.
- `fork:{city}` permits the named city/fork.
- `fork:{city}:{track}` permits the named track inside the named city/fork.

Requests that target a scoped resource pass the concrete scope to policy evaluation. A scoped grant never authorizes another scope. A request without a scope cannot use a scoped grant as if it were global.

`can` remains the single primitive. `batch_can` returns a result per requested check, including scope, rather than collapsing multiple checks with the same permission key into one ambiguous boolean. Callers that need a key summary must explicitly request an `any` or `all` aggregation.

### Delegation and escalation

The first implementation does not expand delegation. Existing delegation tables remain inert until their policy is specified. Grant writers cannot grant a permission they cannot themselves grant, cannot create a global grant from a city-scoped authority, and cannot create or modify break-glass identities. Super-admin changes require a dedicated protected operation and audit event.

## API boundary

`/api/iam` is the canonical surface for permissions, grants, groups, memberships, principal inspection, Discord role mappings, and effective-access inspection. The duplicate `/api/groups` routes are either removed after client migration or reduced to thin compatibility forwarding with identical authorization and audit behavior. There is no second business implementation.

Mutation behavior:

1. Authenticate and resolve the actor.
2. Authorize the exact operation and target scope.
3. Validate referenced users, groups, permissions, and scope format.
4. Apply the state change in one transaction.
5. Write an audit event containing actor, action, target, before/after values, source, scope, and request correlation ID.
6. Commit and return the canonical representation.

Duplicate creates return a stable conflict response. Missing or invalid references return 4xx errors, not database tracebacks. System groups cannot be edited or deleted through ordinary group operations.

## Authentication hardening

- Remove the generic API-key-to-first-super-admin behavior from normal request authentication.
- Keep service authentication separate from human principals, with an explicit service identity and a minimal allowlist of service routes/permissions.
- Continue to verify internal proxy signatures using method, canonical path, user identity, and a short timestamp window.
- Reject ambiguous or malformed authentication combinations rather than silently choosing one credential source.
- Never log API keys, signatures, or raw authorization headers.

## Discord synchronization

Discord role mappings may add or remove only memberships whose source is `discord_sync`. Manual and other managed memberships are preserved. Sync is idempotent, records its actor/source, and cannot assign global permissions directly; global access still requires an explicit internal grant or break-glass operation.

## Operator experience

The IAM console will be reorganized around operator tasks:

- **Overview:** current actor, global roles, city/fork access, and warnings.
- **People and groups:** searchable users/groups with active, source, expiry, and city scope visible.
- **Access review:** effective permissions for a selected person, with the grant path and scope shown.
- **Grants:** create/revoke flows that validate scope and display escalation warnings before confirmation.
- **Discord mappings:** role-to-group mapping with sync source, impact preview, and safe save states.
- **Audit:** recent IAM changes filtered by actor, target, city, and action.

The UI follows the bits&bytes™ brand guideline: burgundy as the structural core, orange for controlled attention, warm neutral surfaces, strong typography, generous whitespace, and restrained texture. It must remain legible and accessible; decorative texture never carries security meaning.

## Data and migration strategy

- Add database constraints or validated application boundaries for principal type and grant references where a polymorphic foreign key cannot express the invariant.
- Add indexes supporting active membership resolution and grant lookup by principal, permission, scope, and expiry.
- Keep existing IDs and permission keys stable.
- Migrate duplicate routes and clients before deleting the old implementation.
- Run a read-only audit/report against existing data before enforcing stricter constraints, surfacing invalid grants, expired memberships, duplicate mappings, and users with unexpected global access.
- Do not mutate production authorization data automatically without an explicit, reviewable migration result.

## Verification

Backend tests must cover:

- inactive users and expired memberships;
- direct, group, scoped, global, and expired grants;
- cross-city denial and track restriction;
- grant validation and escalation denial;
- service authentication isolation;
- audit completeness and transaction rollback;
- Discord sync preserving manual memberships;
- compatibility behavior while `/api/groups` is being retired.

Frontend verification must cover loading, empty, forbidden, conflict, save, and partial-failure states, plus keyboard navigation and responsive layouts. The final pass includes API tests, typecheck, production build, and a rendered IAM walkthrough against seeded data.

## Rollout

1. Run the read-only IAM data audit and review the output.
2. Ship principal/auth/policy hardening behind compatibility-preserving routes.
3. Ship mutation validation and complete auditing.
4. Migrate the dashboard to the canonical API and effective-access views.
5. Exercise the system with representative multi-city fixtures.
6. Disable the unsafe generic API-key path and remove duplicate business logic.
7. Monitor authorization failures, sync drift, audit writes, latency, and error rates before expanding usage.

## Open decisions

- Exact service identities and route allowlists for bots, calendars, and internal jobs.
- Whether existing `Delegation` records are retired or brought into the first-class policy model.
- The authoritative mapping between `Fork` rows and city scope strings, to be resolved from the current schema before migration.
