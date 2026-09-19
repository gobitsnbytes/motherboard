# Motherboard agent memory

Keep this file short. Record only current architecture, durable decisions, active risks, and commands that future work needs. Git history is the session log.

## Current state

- Production branches from `prod`; `main` is not the deployment branch.
- Public web: `https://motherboard.gobitsnbytes.org`; API: `https://api.gobitsnbytes.org`.
- Stack: Bun/Turborepo, Next.js 15 + React 19, FastAPI/Python 3.12, async SQLAlchemy/Alembic, PostgreSQL 16, Redis 7.
- GitHub Actions deploys the API and bot to the VPS on relevant `prod` changes. Vercel owns web deployment.
- Do not store secrets, API keys, raw outreach rows, uploaded documents, rendered artifacts, or runtime databases in Git.

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
- Qenlo is an embedded local retrieval index for the legal agent, not a remote service or system of record. PostgreSQL remains the shared durable boundary.
- The legal mailbox requires authenticated sender validation. Never trust the visible `From` header alone. Legal agent replies enforce anti-loop headers (`Auto-Submitted`, `X-Auto-Response-Suppress`, `Precedence: bulk`), drop self/daemon/bounce messages, strip raw Notion hashes, and synthesize policy answers via SparkCloud AI into responsive branded HTML email templates.
- The old Cal.com callback on `mail.gobitsnbytes.org` is stale. Current callbacks use `/api/calendar/webhooks/calcom/{connectionId}`.

## Production operations

- `deploy/api/deploy.sh` hard-resets the VPS checkout to `origin/prod`, runs migrations, restarts `bnb-api` and `bnb-bot`, then checks `http://127.0.0.1:8000/health` with rollback on failure.
- Dependency installation is conditional on lockfile/manifest changes or a missing environment.
- Database migrations must remain backward compatible with the running application during rollout.
- Never force-push `prod`, discard a dirty production worktree, or deploy without a verified rollback commit.

## Active work

- Semantic OOXML onboarding editor design is approved. Preserve DOCX layout, use versioned semantic anchors, retain audit evidence, and keep Qenlo out of this subsystem.
- Legal email policy replies and attachment review are implemented. Production mailbox secrets and end-to-end mail verification remain operational prerequisites when absent.
- Public scheduling needs server-side slot verification and rate limiting; historical Cal.com duplicates are hidden non-destructively.
- Finance still needs the live RazorpayX boundary and immutable double-entry journal enforcement before it can be treated as a complete banking ledger.

## Maintenance rule

Update this file only when a durable fact changes. Replace stale facts instead of appending session narratives. Keep it under 150 lines.
