# Sentry full-coverage design

## Goal

Finish Sentry instrumentation across Motherboard in this order: FastAPI backend, Next.js frontend, then the Discord bot. The bot remains an `apps/bot` service in the Motherboard monorepo and follows the same release, environment, privacy, and deployment conventions as the rest of the system.

"Full coverage" means unexpected failures reach Sentry with useful stack traces and operational context. It does not mean reporting expected validation errors, authentication failures, or ordinary fallback behavior as issues.

## Principles

- Keep DSNs and auth tokens in deployment environments. Never commit them.
- Use a separate Sentry project for each runtime: API, web, and bot.
- Attach a stable release and environment to every event.
- Disable default PII collection and request-body capture.
- Scrub secrets in URL paths, query strings, headers, logs, and custom context.
- Prefer framework auto-instrumentation at request boundaries. Add explicit capture only where the application catches and swallows an unexpected exception.
- Use modest trace sampling and avoid profiling, replay, metrics, or log ingestion unless they solve a current operational need.

## Phase 1: FastAPI backend

The existing `sentry-sdk[fastapi]` initialization stays before `FastAPI()` creation. Configuration will move behind a small, testable setup boundary so repeated app-factory calls do not create inconsistent SDK state.

The backend setup will add:

- environment and release metadata from existing application/deployment settings;
- a modest configurable trace sample rate;
- request ID correlation on Sentry scopes;
- a `before_send` scrubber for signing and onboarding tokens, sensitive query values, authorization data, and unsafe log context;
- explicit exception capture for unexpected startup services, schedulers, reconciliation loops, and background tasks that currently catch and downgrade failures;
- filtering for expected configuration omissions, validation failures, and deliberate service fallbacks.

Tests will cover disabled configuration, metadata, scrubbing, request correlation, and representative swallowed background failures. Existing API tests must continue to pass.

## Phase 2: Next.js frontend

The current browser, Node, and Edge initialization remains the base. The web phase will make configuration consistent across runtimes and deployment.

The frontend setup will add:

- shared release, environment, and configurable trace sampling;
- production runtime DSNs for browser and server code;
- conditional source-map upload when Sentry build credentials are available;
- safe capture of unexpected proxy timeouts, upstream transport failures, and server 5xx responses;
- route-level error handling where it adds context beyond the global boundary;
- a shared reporting boundary for unexpected client transport failures, without reporting routine 4xx responses.

Docker, Vercel, `.env.example`, and observability documentation will agree on which values are needed at build time and runtime. The auth token remains a build secret and must not become a Docker layer or public environment variable.

Tests will exercise filtering and capture helpers. Type checking and a production build must pass.

## Phase 3: Discord bot as a Motherboard service

The bot will keep its Bun/CommonJS/Discord.js architecture and use `@sentry/node`. The supplied bot DSN will be placed only in ignored local or production environment configuration, never in tracked files.

Instrumentation will be centralized through the bot logger:

- `logger.error` and failed command logging will capture the original `Error` once;
- Discord event handlers, commands, jobs, recording/transcription tasks, and database operations will pass real errors to the central reporter;
- process-level unhandled rejection and uncaught exception handling will capture and flush before preserving fatal exit behavior;
- Discord client and relevant HTTP server failures will be reported;
- release and environment values will match Motherboard conventions;
- shutdown will flush pending events without delaying normal exits indefinitely.

Integration work will remove clear duplication in configuration, API access, deployment metadata, and observability. The bot will continue to access shared Motherboard state through its signed API client rather than reading the production database directly. Broader feature rewrites are outside this Sentry pass.

The bot's env example, README, service unit/deployment path, and tests will be updated together. Plain source files run directly under Bun, so source-map upload is unnecessary unless a later build step starts bundling or minifying them.

## Verification

Each phase ends before the next begins:

1. Run focused tests and static checks.
2. Start the real service through its normal entry point.
3. Trigger a controlled, uniquely named failure through an actual application path.
4. Confirm the event in Sentry, including release, environment, stack readability, and scrubbed context.
5. Remove temporary trigger code.

If authenticated Sentry access is unavailable, code and local transport behavior can still be tested, but ingestion will be reported as unverified. A direct SDK script is not accepted as end-to-end verification.

## Rollout and rollback

All sampling values are environment-configurable. An absent DSN disables Sentry without preventing startup. Each phase is committed separately so it can be reverted without rolling back unrelated application work.

The rollout starts with low trace volume. Error filtering and privacy checks are validated before production deployment. No public debug endpoint remains after verification.

## Out of scope

- Replacing the bot architecture or moving its features into FastAPI.
- Sentry profiling, session replay, custom metrics, user feedback, and full log ingestion.
- Capturing expected 4xx responses or normal control-flow exceptions.
- Provisioning or changing Sentry organization access, billing, alerts, or retention policies.
