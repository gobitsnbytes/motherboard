# Sentry error reporting

The web app uses `@sentry/nextjs` in browser, Node.js, and Edge runtimes. Set `NEXT_PUBLIC_SENTRY_DSN` and `SENTRY_DSN` in the web deployment environment and in an ignored local `apps/web/.env.local` for local testing. `NEXT_PUBLIC_SENTRY_DSN` is embedded at build time. Set `SENTRY_PROJECT` and a secret `SENTRY_AUTH_TOKEN` during production builds to upload source maps; the organization is `gobitsnbytes-foundation`. The SDK samples 10% of traces and leaves default PII collection off. The bot uses `@sentry/node`; set `SENTRY_DSN` in `/opt/bits-bytes-bot/.env` to capture handled bot errors through its logger.

## API (`motherboard-backend`)

`apps/api/app/observability.py` initializes the SDK from `create_app()`, before `FastAPI()` is built. It stays off when `SENTRY_DSN` is blank, and calling `create_app()` again reuses the existing client.

| Variable | Default | Notes |
| --- | --- | --- |
| `SENTRY_DSN` | blank (disabled) | Secret. `/opt/bnb-api/.env` on the VPS, ignored `apps/api/.env` locally. |
| `SENTRY_ENVIRONMENT` | `production` | Set `development` in local `.env` files. |
| `SENTRY_TRACES_SAMPLE_RATE` | 0.02 in production, else 0 | Health checks are never traced. |
| `SENTRY_RELEASE` | `bnb-api@<APP_VERSION>+<sha12>` | The SHA is read from the checkout's `.git` directory. |

What is sent: unhandled request exceptions, via the FastAPI integration; 5xx `HTTPException`s; error-level logs; and caught background failures that call `capture_background_exception()`. That helper covers startup services, EventBus listeners and publish, Cal.com reconciliation, and final legal-reply delivery. Each event is tagged with `service`, plus `subsystem` and `operation` where set. Request events carry the validated `request_id`, which is also returned in the `X-Request-ID` header.

What is not sent: 4xx responses, validation errors, and missing optional configuration. The `app.request` access logger is also ignored, because the integration already captures those failures. Default PII, request bodies, query strings, cookies, local variables, and all headers except a small allowlist are dropped. URLs use the route template (`/sign/{token}`), and `before_send` redacts bearer tokens, credentials in URLs, secret-looking query values, email addresses, and secret-named keys in context.

Profiling is off, and so are Sentry logs and metrics. The API is limited to `MemoryMax=180M` on a 1 vCPU / 1 GB host. Pending events are flushed on shutdown with a 2-second limit.

The Sentry agent plugin is separate from API event reporting. Installing the plugin gives coding agents access to Sentry; it does not configure the running application.

The VPS API `.env` has `SENTRY_DSN` configured. A local SDK verification exception was sent on 2026-09-23 with event ID `706fec2b776a4211b75e5c9d60858c1c`. A direct ingest test to the frontend project returned event ID `a1777cf78a3c400e9ae9998cb063d07e`. These confirm network ingestion, not deployed application coverage. Verify one controlled exception from each running service after deployment.

The backend host had 956 MiB RAM, about 417 MiB available, and 562 MiB of swap in use when checked on 2026-09-23. PostgreSQL, API, bot, mail services, and telemetry share that host. A Dovecot `imap-login` assertion and an authentication worker failure appeared in the host journal; investigate the mail stack before attributing these events to Motherboard API.
