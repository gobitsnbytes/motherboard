# Motherboard Operations Platform — Agent Memory

Persistent log of tasks, architectural decisions, workspace status, and audit findings. Every agent invocation maintains this document.

---

## 1. Project Status

- **Current Phase:** All Phases Completed ✅ (Phases 0–11)
- **Production URL:** `https://motherboard.gobitsnbytes.org` · **API:** `https://api.gobitsnbytes.org`
- **Workspace Hub:** `https://workspace.gobitsnbytes.org` (Nextcloud Suite)
- **Latest Test Baseline:** 247/247 pytest passing (100% green), Next.js 15 build clean (31/31 routes).

### Milestone Checklist

- [x] **Phase 0: Scaffolding** ✅ — Bun/Turborepo workspace + FastAPI (Python 3.12, uv) monorepo.
- [x] **Phase 1: DB Schema** ✅ — SQLAlchemy 2.0 ORM (13 tables), Alembic, idempotent seeder, 8 active routers, auto-migrate lifespan.
- [x] **Phase 2: IAM Module** ✅ — Principal resolver, policy evaluator (`can`/`require_permission`/`batch_can`), audit writer, Pydantic schemas, visual hierarchy tree.
- [x] **Phase 3: Event Bus** ✅ — Redis 7 pub/sub EventBus, typed schemas, graceful fallback.
- [x] **Phase 4: Plugin SDK** ✅ — Dynamic loader, Pydantic lifecycle contracts, active manifest API, permission seeding, route isolation.
- [x] **Phase 5: Provisioning Worker** ✅ — Discord sync worker, APScheduler periodic sync, REST sync routes.
- [x] **Phase 6: Shared UI (`@bnb/ui`)** ✅ — 38 Neobrutalism React components (barrel exports avoided for SSR safety).
- [x] **Phase 7: Web Dashboard (`apps/web`)** ✅ — Next.js 15 App Router, NextAuth v5 (Discord OAuth), double-entry finance ledger, dynamic plugin loader.
- [x] **Phase 8: Core Plugins** ✅ — `email_server`, `minecraft_server` with real telemetry & admin permission gates.
- [x] **Phase 9: Docker & Deployment** ✅ — Multi-stage Dockerfiles, Docker Compose, automated VPS deploy script (`deploy.sh`), Nginx reverse proxy, SSL.
- [x] **Phase 10: chrono ↔ Motherboard Unification** ✅ — Single meetings backend, `AvailabilityGrid`, `ChronoHostGrid`, `ChronoBookingPanel`, RFC-2446 email RSVP, agenda calendar tab.
- [x] **Phase 11: Cockpit Architecture & Neobrutalism Overhaul** ✅ — Swiss Neobrutalism design system (Anton/Inter/JetBrains Mono), Cockpit Debugger (`Ctrl+Shift+D`), Agent Ops Drawer, `bnb-signatures` digital contract engine, Dottr-style Legal Agent.

---

## 2. Architecture & Monorepo Layout

Hybrid monorepo managed via Turborepo (`"packageManager": "bun@1.3.11"`):

```
apps/
  web/          — Next.js 15 (React 19, Tailwind, Framer Motion, Neobrutalism UI)
  api/          — FastAPI backend (Python 3.12, uv, SQLAlchemy 2.0 async, Alembic)
    app/db/       — ORM models, Alembic migrations, idempotent seeders
    app/iam/      — Principal resolver, policy evaluator, audit logger
    app/events/   — Redis EventBus pub/sub
    app/provisioning/ — Discord sync worker & background scheduler
    app/plugin_sdk/  — Dynamic plugin loader & manifest validator
    app/routers/  — auth, iam, finance, sync, users, groups, forks, audit, meetings, signatures, contract_assistant, dyslexic, plugins
    app/services/ — signature_engine, legal_agent, razorpayx_adapter, llm_client
  bot/          — Discord Bot clerk (@bnb/bot, Bun, bun:sqlite, signed HMAC API client)
packages/
  ui/           — @bnb/ui (38 Neobrutalism components)
plugins/        — email_server, minecraft_server, sample_plugin
```

- **Databases:** PostgreSQL 16 (Alembic head: `a9c4e7f1b2d6`) · Redis 7 · Local `bot.db` (`bun:sqlite`, ephemeral bot tables only).
- **Auth:** NextAuth v5 (Discord OAuth) → fire-and-forget upsert to FastAPI `/api/auth/upsert`. Public signing/verification routes bypass NextAuth.
- **Mail & Relay:** Postfix/Dovecot on VPS + Brevo SMTP relay fallback (`smtp-relay.brevo.com:587`). Mandatory CC to `gobitsnbytes@gmail.com` across all systems.

---

## 3. Key Learnings & Engineering Gotchas

1. **Turborepo Workspace Resolution:** Root `package.json` must explicitly specify `"packageManager": "bun@1.3.11"`.
2. **SSR Barrel Import Safety:** `@bnb/ui` barrel imports cause `d.createContext` errors with Next.js `transpilePackages` — use direct component imports or Tailwind utility tokens.
3. **IAM Polymorphic Grants:** `grants` table uses polymorphic `principal_id` (not foreign keys) to unify user and group grants in a single table.
4. **FastAPI Plugin Route Cloning:** APIRouters resolve route dependencies lazily. To enforce plugin permissions without mutating source routers or causing accumulation across reloads, the loader mounts a shallow clone (`copy.copy`) of each `APIRoute` with injected IAM dependencies.
5. **aiosqlite / Pytest Event-Loop Isolation:** Shared SQLAlchemy engines across pytest-asyncio function-scoped loops cause connection leakage and rotating StaleDataErrors. Tests creating isolated transactions must use per-test `create_async_engine(..., poolclass=NullPool)` and explicitly dispose at teardown.
6. **Timezone Normalization (SQLite vs Postgres):** `DateTime(timezone=True)` reads back naive on `aiosqlite`. Normalize with `.replace(tzinfo=timezone.utc)` before Python comparisons.
7. **Database Decoupling:** The Discord bot does not query Postgres directly in production (`usePostgres = false`). It proxies shared state via signed HMAC requests (`callMotherboard`) to Motherboard APIs.
8. **Dual Approval Persistence Pattern:** Money requests >= ₹1L require two distinct approvers (OKF Rule 35). Approvals are persisted as append-only `AuditLog` rows (`action=finance.request.approval_recorded`) and counted via `COUNT(DISTINCT actor_id)`.

---

## 4. Subsystem Specifications

### 4.1 IAM (Identity & Access Management)
- Principal resolver (`principal.py`) resolves user + inherited group permissions.
- Evaluator (`policy.py`) exposes `can(user, perm, resource)`, `require_permission(perm)`, `batch_can(user, perms)`.
- Visual hierarchy at `/dashboard/iam` (`IAMHierarchyVisualizer.tsx`) maps Discord roles to system roles (`Super Admin -> Executive -> Lead -> Member -> Bot`).

### 4.2 Meetings & Chrono v2 Engine
- **Unification:** Both dashboard (`/dashboard/meetings`) and public booking portal (`cal.gobitsnbytes.org`) use Motherboard `/api/meetings` APIs.
- **Availability:** `AvailabilityGrid.tsx` serializes 7-day schedule JSON. Public `/hosts` and `/{slug}/slots` calculate timezone and meeting overlaps.
- **Persistence & OTP:** `GuestVerification` model (`a9c4e7f1b2d6`) stores SHA-256 hashed OTPs (1h TTL). `meetings.recording_metadata` JSON stores audio duration/size.
- **RSVP Widget:** RFC-2446 `multipart/alternative` + `text/calendar; method=REQUEST` MIME generation for native 1-click Gmail/Outlook calendar RSVPs.
- **Transcription:** Fallback pipeline: Gemini 3.5 Flash $\rightarrow$ Gemini 2.5 Flash $\rightarrow$ structured JSON briefs & action items (`/action-items/mine`).

### 4.3 Finance & Double-Entry Ledger
- **Self-Approval Prohibition:** HTTP 403 when `requester_id == actor_id` (IOM v2.0 §3.2).
- **Dual Authorization Band:** Requests $\ge$ ₹1L require 2 distinct approvers before funds move (OKF Rule 35).
- **Section 8 Compliance:** `GET /api/finance/compliance` delivers live compliance attestations, active FY labels (Apr 1–Mar 31), and audit counts.
- **Adapter Seam:** `RazorpayXAdapter` protocol (`PaperLedgerAdapter` for DB virtual accounts; `RazorpayXLiveAdapter` stub for future API activation).
- **FY CSV Export:** `GET /api/finance/reports/fy?fy=YYYY-YY` streams chunked ledger transactions.

### 4.4 Digital Signatures & Legal Agent (`bnb-signatures`)
- **Signature Engine:** PyMuPDF preview/overlay generator, `.docx` to PDF conversion, SHA-256 tamper-evident sealing, and Audit Certificates.
- **Security & DSC:** 6-digit email OTP (2-min expiry), Class 1/2/3 USB token & PKCS#12 `.pfx` software certificate signing (`e5f6a1b2c3d4`).
- **Statutory Framework:** Aligned with IT Act 2000 Sec 10A (electronic contracts) and BSA 2023 Sec 63 (forensic electronic records).
- **Quash / Void & Purge:** `POST /void` invalidates active signing tokens with immutable audit entries; `DELETE` generates a downloadable Certificate of Cancellation before purging disk files.
- **Legal Agent (`legal@gobitsnbytes.org`):** IMAP inbox poller, automatic clause risk analysis (OKF rules), RAG `/ask` over executed contracts, and 3/7/14-day automated signing reminder nudges.

### 4.5 Swiss Neobrutalism Design System
- **Core Tokens:** 2px solid borders (`border-2 border-border`), boxy corners (`rounded-base`), hard offset drop shadows (`shadow-shadow`), dark backgrounds (`#0d0d10`, `#141418`).
- **Typography:** Anton (`font-heading font-black`) for headers, Inter (`font-base`) for UI controls, JetBrains Mono (`font-mono`) for coordinates and metrics, Merriweather for long-form prose.
- **Branding Palette:** Core Burgundy (`#97192C`), Pop Orange (`#FC920D`), Dark Neutral (`#120F0A`), Warm Blank (`#FAF8F5`).

---

## 5. Alembic Migration History

| Migration ID | Description |
|---|---|
| `initial_schema` | Core 13 tables (users, groups, permissions, grants, forks, audit_logs, events, virtual_accounts, etc.) |
| `a1b2c3d4e5f6` | Added `calcom_booking_id` and `calcom_uid` to `EventCache` and meetings schema. |
| `f1a2b3c4d5e6` | Added Digital Signatures tables (`signature_requests`, `recipients`, `fields`, `audit_logs`). |
| `e5f6a1b2c3d4` | Added DSC certificate columns (`dsc_type`, `dsc_issuer`, `dsc_serial`, `allowed_sig_type`). |
| `a7f3c92b1d84` | Contract Assistant ORM tables & clause findings. |
| `h1i2j3k4l5m6` | Dyslexic CRM tables & lead tracking models. |
| `a9c4e7f1b2d6` | Added `guest_verifications` table (hashed OTPs) and `meetings.recording_metadata` JSON column. |

---

## 6. Audit Findings & Production Priorities

Comprehensive read-only production audits (S62–S63) established the following priority backlog for future rollout phases:

1. **Finance & Banking:**
   - Implement real double-entry journal lines (immutable credit/debit pairs) and reconcile historical opening balances.
   - Complete live RazorpayX payout/contact integration with HMAC webhook signature validation.
2. **Signatures & Legal Evidence:**
   - Strengthen public verification endpoints with rate limiting and signed session tokens.
   - Enforce mandatory org countersignature in final completion workflow before sealing.
   - Update compliance copy to reference BSA 2023 Section 63 certificate requirements.
3. **Meetings & Scheduling:**
   - Ensure PostgreSQL is the single source of truth for the bot scheduler to prevent SQLite mirror split-brain.
   - Enforce database-level UNIQUE constraints on `calcom_booking_id` to eliminate poll duplication.
   - Add rate-limiting and server-side slot verification to public booking endpoints.
4. **Plugins:**
   - Enforce explicit `*.admin` permission checks on destructive routes across all plugin manifests.

---

## 7. Session Log

### Pre-Production (S1–S33, up to 2026-06-25)
- Scaffolding, Phase 1 (13 ORM tables), Phase 2 (IAM), Phase 3 (EventBus), Phase 4 (Plugin SDK), Phase 7 (Finance shell), VPS deployment, Nginx SSL.

### S34–S44 (2026-06-26 to 2026-07-19)
- **S34–S36:** Discord bot refactored to proxy all operations to Motherboard via HMAC `callMotherboard`; audio transcription offloaded to FastAPI; Bun test suite hardened (208/208 green).
- **S37–S39:** Cal.com rescheduling webhook (`BOOKING_RESCHEDULED`); voice channel auto-join cache resolution; Docker compose Redis URL fix.
- **S40–S41:** Meetings N+1 query optimization; Cal.com schema migration (`a1b2c3d4e5f6`); Gemini 3.5 $\rightarrow$ 2.5 Flash transcription fallback; programmatic API key auth.
- **S42–S44:** Consolidated bot into monorepo (`apps/bot`); migrated SQLite to `bun:sqlite`; built public availability slots API; RFC-2446 email RSVP widget.

### S45–S55 (2026-08-02 to 2026-08-09)
- **S45–S48:** Launched `bnb-signatures` (`f1a2b3c4d5e6`); unified Chrono meetings UI with `AvailabilityGrid`; responsive layout overhaul; Dyslexic CRM routing.
- **S49–S52:** Added email OTP & Class 1/2/3 DSC support (`e5f6a1b2c3d4`); database persistence for Contract Assistant; contract void/purge; Cockpit UI & IAM visualizer.
- **S53–S55:** Integrated Nextcloud workspace (`workspace.gobitsnbytes.org`) as team operations hub; white-labeling & 5TB Google Drive mount; PHP 8.3 OPCache & JIT tuning.

### S56–S61 (2026-08-19 to 2026-08-26)
- **S56–S57:** Signature verification engine overhaul (real SHA-256 hashing); statutory compliance checks; Brevo SMTP relay fallback; mandatory `gobitsnbytes@gmail.com` CC policy.
- **S58 (Agent D):** Built `MeetingsAgendaCalendar.tsx`; wired Calendar tab; added `RecordingChip`; tokenized meetings UI (zero hex colors).
- **S58 (Agent C):** Implemented self-approval prohibition (403), dual authorization band (>= ₹1L via AuditLog), Section 8 compliance endpoint, FY CSV stream export, and `RazorpayXAdapter` seam.
- **S59 (Agent A):** Created persistent `guest_verifications` table (SHA-256 OTPs, `a9c4e7f1b2d6`); added `recording_metadata` JSON column; built `/action-items/mine` endpoint.
- **S60 (Agent B):** Hardened plugins with live SSL/DNS checks, honest metrics, and route-clone IAM permission enforcement.
- **S61 (Agent F):** Implemented `legal@gobitsnbytes.org` Legal Agent with IMAP polling, OKF RAG `/ask`, contract analysis, and 3/7/14d reminder nudges.

### S62–S64 (2026-08-26)
- **S62–S63:** Executed comprehensive read-only audits across Finance, Signatures, Meetings, and Plugins; documented production gaps and architectural backlog.
- **S64:** Full Swiss Neobrutalism UI overhaul across all 31 Next.js routes in `apps/web` (2px borders, hard shadows, Anton/Inter/JetBrains Mono typography). All 247 backend tests and web build passing.

### S65 (2026-09-09)
- Read-only Ponytail whole-repository audit completed. Confirmed simplification candidates include an orphaned Three.js background, an unused text animation, an oversized unused subset of `@bnb/ui`, duplicate npm/Bun lockfiles for the bot, and tracked generated signature PDFs. No code changes were applied.

### S66 (2026-09-09)
- Branded public form pages with the official bits&bytes™ logo/favicon, metadata, brand-neutral shell colour, and required legal footer. Preserved the existing editorial form composition. Production deployment: commit `8376d1d` on `origin/prod`; public form routes and API proxy returned 200 after deployment.

### S67 (2026-09-09)
- Re-audited production branch topology before deployment. `origin/prod` is the live API deployment branch and is ahead of local `main`; preserved local IAM work on `codex/pre-prod-sync` and `codex/iam-overhaul-prod` rather than force-pushing stale history.
- Hardened production-branch IAM in an integration branch: explicit non-admin API service identity, active/expired principal checks, scope-safe policy evaluation, mutation audit coverage, and mixed-credential rejection. Live read-only inspection confirmed active users exist, but no user is designated as a service principal; do not guess one before deploying this backend change.
- Ported the safe Members/Audit operator improvements onto the production UI line: typed records, retryable failures, skeleton loading, empty states, and accessible table captions. This is the next safe production checkpoint.

### S68 (2026-09-09)
- Fixed the production IAM route so it actually renders the IAM directory alongside the hierarchy and Discord role mapper. Added functional group search, retryable load errors, skeleton loading, and an accessible table caption. Production web build remains green; checkpoint is ready to push.

### S69 (2026-09-09)
- Reset the redesign direction after review: the app was still visually fragmented despite the safe IAM checkpoint. Added a shared product design contract and began the real shell overhaul: burgundy control rail, warm document canvas, consistent topbar controls, stronger navigation hierarchy, and restrained page-entry motion. This is a broad UI pass and must be validated across routes before more backend work is pushed.

### S70 (2026-09-09)
- Reworked Settings operation feedback to use inline success/error notices instead of browser-native alerts. Manual sync, cache reset, permission rebuild, and sync-history clearing now expose actionable status inside the page while preserving explicit confirmation for destructive actions.

### S71 (2026-09-09)
- Continued the daily-operator pass across Overview, Members, and IAM: removed emoji/implementation copy, replaced Overview browser alerts with inline status feedback, improved page-level hierarchy and copy, and made the network/operator purpose explicit.

### S72 (2026-09-09)
- Aligned the separate Finance shell with the same product language: burgundy navigation rail, warm canvas header, shared focus/active-state treatment, and consistent mobile navigation controls.

### S73 (2026-09-09)
- Hardened the IAM Discord role mapping surface: removed internal implementation badges, clarified the audit behavior, extracted a reusable retryable loader, and added an in-page retry action for failed role/group/mapping fetches.

### S74 (2026-09-09)
- Reworked Meetings mutation feedback to use a shared inline notice for instant meetings, scheduling, availability, notification preferences, cancellation, and rescheduling. Browser alerts remain only for explicit cancellation confirmation.

### S75 (2026-09-09)
- Reworked Signatures mutation feedback to use inline success/error banners for counter-signing, invitation resend, voiding, and purge/export actions. Explicit confirmation remains for legally destructive operations.

### S76 (2026-09-09)
- Corrected IAM hierarchy truthfulness: removed the unverified “2-Way Discord Sync Active” claim and hard-coded permission list, added API error/retry states, and now display only verified group counts and sync feedback.

### S77 (2026-09-09)
- Began normalizing all Finance routes into the shared warm document canvas. Finance panels and form fields now inherit paper surfaces and dark readable text instead of the legacy second dark theme, while burgundy/orange actions remain available for emphasis.

### S78 (2026-09-09)
- Reworked the public login surface from a generic centered card into a responsive bits&bytes™ access composition: burgundy brand panel, warm paper auth panel, explicit identity/scope/audit framing, clearer copy, and logged invite-only access language.

### S79 (2026-09-09)
- Production verification after the login push exposed that `motherboard.gobitsnbytes.org` is still serving the previous web bundle. The repository has no Vercel project link or web deploy workflow; the Vercel CLI is unauthenticated and was stopped without entering credentials. Git `prod` remains authoritative for the code, but web deployment wiring must be connected before claiming browser verification of new UI.

### S80 (2026-09-09)
- Reworked the public home and not-found surfaces to remove unverified “system online,” coordinate, and compliance claims. The home page now explains identity, coordination, and evidence using the shared burgundy/paper system, with a clear Discord access path and public-form path.

### S81 (2026-09-09)
- Extended the shared internal canvas normalization so older dark utility classes and muted white text resolve to the warm paper system. This reduces the split-brain look across legacy audit, finance, signatures, and CRM surfaces without changing the public routes or sidebar chrome.

### S82 (2026-09-09)
- Hardened IAM authorization semantics: expired memberships no longer resolve into groups, scoped grants cannot satisfy an unscoped check, and batch authorization now returns an independent result for each permission/resource pair. Added input constraints for permission, grant, and group identifiers. The API-key service identity fallback remains isolated until a real non-admin production service principal is configured.

### S83 (2026-09-09)
- Continued IAM hardening: permission/grant/group/membership/Discord-role mutations now validate referenced records, reject expired grants or memberships, and write audit entries for access changes. The service-identity fallback remains intentionally unmerged pending production configuration.

### S84 (2026-09-09)
- Local browser verification found stale Overview copy claiming specific infrastructure and statutory compliance. Replaced it with truthful connected-service labels and a restrained operational footer; removed fake telemetry/legal badges from the daily workspace surface.

### S85 (2026-09-09)
- RLVR on live IAM exposed one remaining overclaim: the action said “2-Way Discord Sync” even though the surface triggers a role refresh. Renamed it to “Refresh Discord roles” so the control matches the verified behavior.

### S86 (2026-09-09)
- RLVR on live Meetings found repeated records flooding the operator view. Added non-destructive client-side deduplication by meeting identity/schedule/room, a visible warning with the duplicate count, and left source records untouched for a later data cleanup pass.

### S87 (2026-09-09)
- RLVR on live Finance found the daily dashboard presenting configured policy flags as legal/compliance verification, including a licence number. Renamed the surface to “Governance checks,” changed the status to “Policy configured,” removed the licence claim, and kept the no-real-money disclaimer and operational controls intact. Typecheck and diff checks pass.

### S88 (2026-09-09)
- RLVR on live Settings found more unverified operational/legal wording. Changed region to an operating-region label, removed the compliance claim, made Discord/API labels describe observed connectivity rather than inferred service state, and simplified the database label. Dark legacy cards remain a follow-up visual normalization target.

### S89 (2026-09-09)
- Continued the visual normalization pass in IAM role mappings and Settings: replaced legacy near-black panels with shared paper surfaces, corrected foreground contrast, and removed a duplicate text utility. Production IAM now shows the truthful “Refresh Discord roles” action; many Discord roles remain intentionally unmapped and require operator decisions rather than automatic assignment.

### S90 (2026-09-09)
- Production verification caught one remaining Finance wording leak: the new Governance checks card still rendered the API status value “compliant.” Mapped that display to “configured” or “review” so the UI does not turn a policy configuration result into a legal claim.

### S91 (2026-09-09)
- RLVR on a public certificate exposed signatory email addresses and IP addresses in the public audit trail. Masked emails and replaced public IP output with a private-record notice; the underlying audit data remains available to authorized internal systems.

### S92 (2026-09-09)
- Fixed the root cause behind the public certificate privacy issue. Public signature verification responses now use dedicated redacted schemas: no access tokens, raw emails, IP addresses, user agents, or unredacted audit details leave the API. Added regression assertions; the signature router suite passes 11 tests.

### S93 (2026-09-09)
- Added IAM role-mapping guardrails in the operator surface: privileged Discord mappings now show a review banner and break-glass label instead of looking like ordinary saved mappings. This is intentionally non-mutating; existing access assignments still require an explicit operator decision.

### S94 (2026-09-09)
- Live IAM RLVR confirmed a canonical data mismatch: the seeded `Executive Leadership` Discord role was mapped to `sg_super_admin` instead of `sg_executive`. Added a narrowly scoped reversible Alembic migration that repairs only that role ID when the incorrect Super Admin target is present.

### S95 (2026-09-09)
- Production verification completed for the IAM repair. The backend pipeline passed and deployed commit `7ee99d1`; API and web health endpoints return 200. Authenticated live IAM now shows `Executive Leadership` mapped to its intended `Executive Leadership` group, while only the explicit `admin` role remains mapped to Super Admin and is visibly marked break-glass. The new privileged-mapping review banner is live.

### S96 (2026-09-09)
- Tightened the shared dashboard shell: the top bar now exposes the current workspace section/page, no longer presents the DYSLEXIC link as a fake live-status indicator, and reserves space for the mobile navigation trigger so controls do not collide. Typecheck and diff checks pass.

### S97 (2026-09-09)
- Removed the encoded SMTP credential and automatic `.env` mutation from the VPS deploy script. Production mail settings now come only from the server environment; deployment still performs a non-secret SMTP preflight when credentials are present. This closes a credential-exposure and configuration-drift path discovered while tracing the separate Vercel web deployment.

### S98 (2026-09-09)
- Continued the visual overhaul on the live Overview command center: replaced legacy near-black content cards, headers, list rows, action controls, and dialogs with the warm paper, burgundy, and orange brand system. Data loading, sync, fork creation, invitation, and navigation behavior are unchanged. Local typecheck/build passed before deployment preparation.
