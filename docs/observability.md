# Sentry error reporting

Motherboard reports to three Sentry projects in the `gobitsnbytes-foundation` organization: `motherboard-backend` for the API, `motherboard-frontend` for the web app, and `discord-bot-utility` for the bot. DSNs live only in ignored local env files or deployment environments.

## Web (`motherboard-frontend`)

`instrumentation-client.ts`, `sentry.server.config.ts`, and `sentry.edge.config.ts` each call `Sentry.init` once with the options in `sentry.shared.ts`. That file holds only public values because it ships to the browser. Events carry the SDK's `runtime` tag (browser, node, or edge).

| Variable | When | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_SENTRY_DSN` | build | Used by all three runtimes. `SENTRY_DSN` stays reserved for the API, which shares the root `.env` under Compose. |
| `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` | build | Blank: 0.05 in production, 0 elsewhere. |
| `SENTRY_ENVIRONMENT` | build | Blank: `VERCEL_ENV`, then `production` for production builds. |
| `SENTRY_RELEASE` | build | Blank: `bnb-web@<version>+<sha12>` from `VERCEL_GIT_COMMIT_SHA`, `GITHUB_SHA`, or `GIT_SHA`. |
| `SENTRY_AUTH_TOKEN` | build, secret | Enables source-map upload; maps are deleted after upload. Without it, the build skips upload. |

On Vercel, set `NEXT_PUBLIC_SENTRY_DSN` and a sensitive `SENTRY_AUTH_TOKEN` for Production and Preview; Vercel supplies the commit SHA and environment. For Docker, pass the public values as build args and the token as a BuildKit secret (`docker build --secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN`). Compose wires both up, so the token never becomes an image layer. Turbo declares these variables for `build`, and passes the token through without hashing it.

What is reported:
- Server errors, through `onRequestError`.
- Client render errors in the segment boundaries (`dashboard`, `finance`, `onboarding`, `(public)`) and `global-error.tsx`. Errors with a `digest` are skipped because the server already reported them.
- API proxy transport failures, timeouts, interrupted bodies, and upstream 502/504.
- Auth bridge outages.

Proxy events are tagged with `operation`, `upstream`, `http.method`, and a normalized `http.route` (`/signatures/sign/:token`). Upstream 4xx responses are not reported. Neither are upstream 500s and 503s: the API reports its own 500s, and its 503s are deliberate. Browser fetch helpers don't report either, because every backend call passes through the proxy. Cookies, request bodies, query strings, users, and all headers except a small allowlist are removed before sending.


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
