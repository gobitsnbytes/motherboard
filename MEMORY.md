# Motherboard agent memory

Keep this file short. Record only current architecture, durable decisions, active risks, and commands that future work needs. Git history is the session log.

## Current state

- Production branches from `prod`; `main` is not the deployment branch.
- Public web: `https://motherboard.gobitsnbytes.org`; API: `https://api.gobitsnbytes.org`.
- Stack: Bun/Turborepo, Next.js 15 + React 19, FastAPI/Python 3.12, async SQLAlchemy/Alembic, PostgreSQL 16, Redis 7.
- GitHub Actions deploys the API and bot to the VPS on relevant `prod` changes. Vercel owns web deployment.
- Do not store secrets, API keys, raw outreach rows, uploaded documents, rendered artifacts, or runtime databases in Git.
- The API has opt-in Sentry error reporting through `SENTRY_DSN`; tracing, profiling, and default PII collection are disabled. See `docs/observability.md`. The Sentry agent plugin is installed separately for Codex and Claude Code.

## Commands

```powershell
bun install --frozen-lockfile
bun run typecheck
bun run lint
bun run build
uv sync --project apps/api --frozen
uv run --project apps/api python -m pytest apps/api/tests
```

Focused API tests should run from `apps/api` when their imports or relative data paths require it.

## Repository map

- `apps/web`: Next.js dashboard and public portals.
- `apps/api`: FastAPI application, routers, services, models, migrations, and tests.
- `apps/bot`: Discord bot and signed Motherboard API client.
- `packages/ui`: shared React components.
- `plugins`: optional Motherboard plugins.
- `data/company-knowledge`: legal/OKF knowledge source.
- `templates`: onboarding DOCX sources copied by `docker/api.Dockerfile`.
- `deploy/api`: VPS setup, systemd, Nginx, and rollout scripts.

## Durable contracts and gotchas

- IAM is city/resource scoped. A scoped grant must never satisfy a global permission check. Service auth uses explicit `API_SERVICE_USER_ID` and fails closed.
- `grants.principal_id` is intentionally polymorphic across users and groups.
- Plugin routers are shallow-cloned before IAM dependencies are injected; mutating source routers accumulates dependencies across reloads.
- Async SQLite tests need per-test engines with `NullPool`; SQLite returns naive datetimes, so normalize to UTC before comparisons.
- The bot does not read production PostgreSQL directly. Shared state crosses signed HMAC API calls.
- Avoid `@bnb/ui` barrel imports in server-rendered code; direct imports prevent React context failures.
- Finance requests at or above INR 1 lakh require two distinct approvers and prohibit self-approval.
- Onboarding Forms 1-5 are the active package. Form 6 is a separate minor event-consent flow. Generated onboarding files live under `apps/api/data/onboarding/` and are never source assets.
- Onboarding telephone fields are stored in canonical Indian E.164 form. Unsigned signing requests may be audited and voided back to `approved`; signed requests cannot be rolled back, and compilation refuses duplicate active signature requests. OOXML multiline controls must replace prior run content rather than append across revisions.
- Onboarding reviewers are real Discord-linked users whose synced IAM principal has `onboarding.review`; no seed profiles, email aliases, or Super Admin bypass populate the picker. Executive Leadership and Department Leads receive that permission through Discord-synced groups. A permissioned case creator may assign themself. Reviewer name, email, avatar, and title come from that linked user's profile. Ages 13-17 require a separately scoped guardian portal using `2_Parents_Consent_.docx`, and ages 16-17 add the minor as a consent co-signer. Fork leads may invite teammates only after submitting their full lead packet; minor teammates receive the same linked guardian flow.
- The Members page is a signed-in people directory: it lists only active users linked through Discord OAuth, displays profile identity alongside Discord identity, and derives role badges only from active `discord_sync` IAM memberships. The generic users API remains available for operational selectors.
- Qenlo vector DB is dropped in favor of native Open Knowledge Format (OKF) concept retrieval (`OKFKnowledgeStore.search_concepts`), matching titles, tags, descriptions, and Markdown bodies directly with zero external vector DB or embedding costs.
- The legal mailbox parses both plain text and HTML email bodies (stripping reply quotes and signatures), enforces anti-loop headers (`Auto-Submitted`, `X-Auto-Response-Suppress`, `Precedence: bulk`), drops self/daemon/bounce messages, and synthesizes policy answers via SparkCloud AI into responsive branded HTML email templates following Humanizer anti-AI guidelines.
- Mailroom is the end user webmail plugin. Dovecot IMAP remains the only message store; Motherboard keeps encrypted mailbox credentials, OTP challenges, and writing preferences, but never a durable copy of message content. It reuses the Motherboard session rather than issuing its own cookie, so the design doc's `mailroom_sessions` table was not built.
- The legal knowledge base synchronizes directly with the active Notion Wiki, e-AOA, and e-MOA, indexed with rich OKF frontmatter for zero-cost deterministic search.
- The old Cal.com callback on `mail.gobitsnbytes.org` is stale. Current callbacks use `/api/calendar/webhooks/calcom/{connectionId}`.

## Production operations

- `deploy/api/deploy.sh` hard-resets the VPS checkout to `origin/prod`, runs migrations, starts the replacement API on the idle port (8000/8001), waits for liveness and readiness, switches Nginx, verifies public health, and only then retires the old worker. Failed candidates leave the previous worker serving traffic.
- Dependency installation is conditional on lockfile/manifest changes or a missing environment.
- Database migrations must remain backward compatible with the running application during rollout.
- Never force-push `prod`, discard a dirty production worktree, or deploy without a verified rollback commit.
- On `bnb-backend`, `mail.gobitsnbytes.org` TLS is managed by Certbot's Nginx plugin under the `mail.gobitsnbytes.org-0001` lineage; the unsuffixed live path is a symlink. Certbot's twice-daily timer is enabled, and `/etc/letsencrypt/renewal-hooks/deploy/reload-mail-tls` reloads Postfix and Dovecot after each successful renewal.
- On `bnb-backend`, the `bnb-bot` uses `hello@gobitsnbytes.org` for SMTP. Any reset of that mailbox must update `SMTP_PASS` in `/opt/bits-bytes-bot/.env` and restart `bnb-bot`.
- `seed_okf_rules()` previously rewrote 35 tracked legal-rule files at API startup, changing CRLF to LF on the VPS. It now creates only missing rules. Deployment/setup preflight guards stop on dirty checkouts; the existing VPS line-ending changes still need byte-preserving backup and reconciliation before the next deploy.
- `SENTRY_DSN` is configured in the VPS API `.env` (not Git). A controlled local SDK exception was sent as event `706fec2b776a4211b75e5c9d60858c1c`; the API SDK integration is not deployed yet. The Next.js SDK now covers browser, Node, and Edge runtimes, with DSNs in ignored `apps/web/.env.local`; its production build passes. A direct frontend ingest test was accepted as event `a1777cf78a3c400e9ae9998cb063d07e`. Vercel CLI currently authenticates as `a3ro-dev` and cannot retrieve the linked `web` project settings, so production web environment variables are not yet configured.

## Active work

- Semantic OOXML onboarding editor design is approved. Preserve DOCX layout, use versioned semantic anchors, retain audit evidence, and keep Qenlo out of this subsystem.
- Legal email policy replies and attachment review are implemented. Production mailbox secrets and end-to-end mail verification remain operational prerequisites when absent.
- Public scheduling needs server-side slot verification and rate limiting; historical Cal.com duplicates are hidden non-destructively.
- Finance still needs the live RazorpayX boundary and immutable double-entry journal enforcement before it can be treated as a complete banking ledger.
- TypeSafe AI use-case assessment: the lowest-friction integration point is the existing contract-assistant/legal-agent pipeline (classification, risk scoring, routing/escalation, retrieval, and verification); finance authorization must remain deterministic, with semantic scoring limited to triage/explanations until separately validated.

## Maintenance rule

Update this file only when a durable fact changes. Replace stale facts instead of appending session narratives. Keep it under 150 lines.
