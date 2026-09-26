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
- The blue/green candidate has a 256 MB hard memory limit and 192 MB soft limit. Failed health checks print privileged `systemctl` status and only the current rollout's journal entries before rollback.
- Blue/green cutovers must enable the active `bnb-api@PORT` unit and disable the legacy/prior unit; otherwise a VPS reboot can leave Nginx pointing at an inactive port. Candidate validation includes `/api/openapi.json` before cutover so schema failures rollback and the cold schema cache is warmed off-traffic.
- Dependency installation is conditional on lockfile/manifest changes or a missing environment. CI runs the Discord bot's Bun test suite before the VPS deploy job, alongside Ruff and the API migration/test gate.
- `.github/workflows/web-ci.yml` runs web typecheck, Bun tests, and a production build for web/UI changes. It is separate from the VPS API deploy workflow, so web-only pushes do not restart backend services.
- Bot mail option tests call the pure `buildMailOptions()` helper. The previous suite-wide Nodemailer mock behaved differently on Linux and attempted SMTP; avoid network-backed test assertions for mail option shape.
- SQLite files used by pytest must include `PYTEST_XDIST_WORKER`; shared filenames race under `pytest -n auto` and can fail setup with duplicate-table errors.
- Database migrations must remain backward compatible with the running application during rollout. The deploy script runs Alembic only; it no longer calls `Base.metadata.create_all()` to silently fill missing tables. CI's `alembic check` is the schema gate.
- Never force-push `prod`, discard a dirty production worktree, or deploy without a verified rollback commit.
- On `bnb-backend`, `mail.gobitsnbytes.org` TLS is managed by Certbot's Nginx plugin under the `mail.gobitsnbytes.org-0001` lineage; the unsuffixed live path is a symlink. Certbot's twice-daily timer is enabled, and `/etc/letsencrypt/renewal-hooks/deploy/reload-mail-tls` reloads Postfix and Dovecot after each successful renewal.
- On `bnb-backend`, the `bnb-bot` uses `hello@gobitsnbytes.org` for SMTP. Any reset of that mailbox must update `SMTP_PASS` in `/opt/bits-bytes-bot/.env` and restart `bnb-bot`.
- `seed_okf_rules()` previously rewrote 35 tracked legal-rule files at API startup, changing CRLF to LF on the VPS. It now creates only missing rules. Deployment/setup preflight guards stop on dirty checkouts. The line-ending-only VPS changes were backed up to `/home/ubuntu/okf-rules-line-endings-20260923.tar.gz` and reconciled; the VPS checkout was clean at the 2026-09-23 rollout.
- `SENTRY_DSN` is configured in the VPS API and bot `.env` files (not Git). API and bot SDK code is deployed on the VPS. A local API SDK exception was sent as event `706fec2b776a4211b75e5c9d60858c1c`; a direct frontend ingest test was accepted as `a1777cf78a3c400e9ae9998cb063d07e`. Verify production runtime events separately. The Next.js SDK covers browser, Node, and Edge runtimes, with DSNs in ignored `apps/web/.env.local`; production web environment and build configuration is under active work.

## Active work

- Sentry coverage is implemented across the API, web, and bot. Each runtime uses its own project and shared release/environment/privacy conventions; expected 4xx and control-flow failures stay out of issue reporting. Safe structured Sentry Logs cover API requests and handled agent failures, all bot logger calls and command lifecycle events, and web proxy/auth failures. SparkCloud spans carry GenAI model/provider and token counts without prompts or outputs. Commits through `413fa98` were pushed to `prod` on 2026-09-25; CI and VPS deploy succeeded for `413fa98`, GitHub reports the Vercel Production deployment successful, and public API readiness/OpenAPI/web returned 200. Production Sentry log ingestion still needs a fresh read-only token to verify. The public OpenAPI 500 tracked as `MOTHERBOARD-BACKEND-8` was reproduced and fixed in the Minecraft plugin (`da5f83b`). A public health check timed out once despite a healthy local candidate, so `413fa98` retries before rollback.
- EventBus Redis pub/sub timeout recovery now probes its own socket and closes failed subscriptions before retrying. It emits static connected/reconnecting Sentry logs and keeps exception text out of local warnings; focused observability and SSE tests passed. Commit `1bc7d41` deployed successfully.
- The calendar admin booking list must map `provider_booking_uid`/`start_at`/`end_at` to its public `uid`/`start`/`end` response fields explicitly; raw provider payloads never belong in that response.
- The Discord weekly brief now sends Sentry Cron check-ins for start and outcome, including missing-channel and caught-provider failures, under `bot-weekly-brief`. The bot test suite passed; production rollout is pending.
- Semantic OOXML onboarding editor design is approved. Preserve DOCX layout, use versioned semantic anchors, retain audit evidence, and keep Qenlo out of this subsystem.
- Legal email policy replies and attachment review are implemented. Production mailbox secrets and end-to-end mail verification remain operational prerequisites when absent.
- Public scheduling needs server-side slot verification and rate limiting; historical Cal.com duplicates are hidden non-destructively.
- Finance has an append-only double-entry journal (`app/finance`, `fin_*` tables, Postgres triggers block UPDATE/DELETE of posted rows), April-March period locks, maker-checker vouchers, s.269ST/s.40A(3)/FCRA guards, and journal-derived statutory reports. RazorpayX is a stub (`payout_provider.py`) returning 503; TDS defaults and fund mapping need CA review before these are the books of record.
- All LLM features use SparkCloud only (`services/llm_client.py`, chat-only, no search or audio). Meetings transcription remains on Gemini because SparkCloud has no audio endpoint.
- TypeSafe AI use-case assessment: the lowest-friction integration point is the existing contract-assistant/legal-agent pipeline (classification, risk scoring, routing/escalation, retrieval, and verification); finance authorization must remain deterministic, with semantic scoring limited to triage/explanations until separately validated.

## Maintenance rule

Update this file only when a durable fact changes. Replace stale facts instead of appending session narratives. Keep it under 150 lines.

## 2026-09-25 Sentry continuation (legal agent shutdown)
- Sentry MCP connected. Queried unresolved production issues in motherboard-backend, motherboard-frontend, and discord-bot-utility. Backend issue MOTHERBOARD-BACKEND-A showed APScheduler reporting CancelledError while legal inbox polling was interrupted during deploy shutdown; frontend and bot had no unresolved issues in the 24-hour query. Redis readiness timeout and historical OpenAPI/pubsub issues remain separate follow-ups.
- Added normal cancellation handling to both legal agent scheduled job wrappers and changed handled-failure log text to exception class only. Existing ai.pipeline transaction and capture_background_exception for real failures remain.
- Added parametrized cancellation regression tests; legal-agent suite 27 passed, Ruff passed, staged diff reviewed with no findings. Atomic commit a11d1f9 pushed to prod. CI/CD run 36106435873 was queued at last check.
- Preserved preexisting AGENTS.md and MEMORY.md modifications and untracked .github/workflows/web-ci.yml; MEMORY.md remains unstaged.

- First CI run 36106435873 failed Ruff format check on the newly added test. Formatted only the test hunk, reviewed it, committed cabce09, and pushed prod. Replacement run 36106535461 was pending at last check.

## 2026-09-25 Calendar routing diagnosis
- The shared account's event type 5707357 uses Cal.com's current `{type: integration, integration: google-meet}` location shape. Commit `8b131ac` fixed the backend member validator and deployed successfully. Both production pools (`sponsors`, `onboarding`) now have one active host.
- Commit `877dbba` redesigned public booking pages with a month calendar, time list, details step, responsive layout, and bits&bytes logo; it added GET `/api/calendar/public/{pool_slug}` metadata. Web production deployment 6656593562 and API CI/deploy run 36111835506 succeeded; VPS HEAD matched. Both production pool descriptions now append the exact foundation branding and CIN text; the UI shows the short description above the calendar and the legal text in its footer. Public API metadata for both pools returned `ready: true`, both public pages returned 200, and API readiness returned 200 after rollout. Focused API tests (8), web typecheck, and web build passed. Preserve unrelated working-tree changes.


## 2026-09-25 Sentry Agent Tracing and Conversations
- Read https://skills.sentry.dev/instrument and current Python Agent Tracing/manual instrumentation docs. Confirmed the existing FastAPI runtime owns Sentry, send_default_pii is false, and the installed SDK is 2.70.0 with set_conversation_id but start_span does not support an attributes keyword.
- Changed SparkCloud model span to gen_ai.chat, added gen_ai.invoke_agent around legal /ask synthesis, and an optional UUID conversation_id on /ask. Both web chat entry points send stable per-open-chat UUIDs. Handled synthesis failures now set error.type and report a privacy-safe agent failure. Prompt and response content remain excluded.
- Legal Agent suite 27 passed; Ruff checks and test formatting passed; web typecheck passed. Web lint script cannot run because ESLint is not installed (preexisting tooling issue). Reviewed changed diff for input validation, privacy, and span ownership. Committed d749d43 and 9f92c78, pushed prod. CI/CD run 36107602034 queued at last check. Sentry span search had no gen_ai.invoke_agent results yet before rollout/user traffic.
- Confirmed the deployed Discord bot is a separate repository, gobitsnbytes/bitsnbytes-discord-utility. The apps/bot copy tracked in Motherboard is not proof of deployment. Updated observability docs to clarify this. Preserved preexisting unstaged AGENTS.md and MEMORY.md edits and untracked web-ci.yml.

