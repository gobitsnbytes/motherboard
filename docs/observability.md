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

Sentry Logs records static proxy and auth bridge failures with a failure class and optional status code. The shared log hook rejects all other messages and attributes, so profiles, route values, tokens, and upstream response bodies do not enter logs. JavaScript SDK v11 captures explicit `Sentry.logger` calls without an `enableLogs` option.


## API (`motherboard-backend`)

`apps/api/app/observability.py` initializes the SDK from `create_app()`, before `FastAPI()` is built. It stays off when `SENTRY_DSN` is blank, and calling `create_app()` again reuses the existing client.

| Variable | Default | Notes |
| --- | --- | --- |
| `SENTRY_DSN` | blank (disabled) | Secret. `/opt/bnb-api/.env` on the VPS, ignored `apps/api/.env` locally. |
| `SENTRY_ENVIRONMENT` | `production` | Set `development` in local `.env` files. |
| `SENTRY_TRACES_SAMPLE_RATE` | 0.02 in production, else 0 | Health checks are never traced. |
| `SENTRY_RELEASE` | `bnb-api@<APP_VERSION>+<sha12>` | The SHA is read from the checkout's `.git` directory. |

What is sent: unhandled request exceptions, via the FastAPI integration; 5xx `HTTPException`s; error-level logs; and caught background failures that call `capture_background_exception()`. That helper covers startup services, EventBus listeners and publish, Cal.com reconciliation, and final legal-reply delivery. Each event is tagged with `service`, plus `subsystem` and `operation` where set. Request events carry the validated `request_id`, which is also returned in the `X-Request-ID` header.

The EventBus reports static connected/reconnecting logs. Its Redis pub/sub listener probes the same connection after an idle timeout and closes a failed connection before retrying; exception details are reduced to the class in local warnings.

The shared SparkCloud client adds a `gen_ai.chat` span with the configured model name and Sentry's GenAI model, provider, operation, and token usage attributes. The legal `/ask` route wraps synthesis in a `gen_ai.invoke_agent` span. Both web chat entry points send an opaque UUID per open conversation so Sentry can group turns. It never adds prompts, model responses, or provider error bodies to spans, logs, or raised errors; `send_default_pii` remains disabled. This client is used by contract analysis, the legal agent, Dyslexic research and email drafting, and the mailroom assistant.

The legal inbox and Dyslexic research jobs create sampled `ai.pipeline` transactions. Handled model failures in the legal agent, company research, and email drafting report a static operation name and failure class via `capture_agent_failure()`, without including prompts, company names, contract text, or model responses in Sentry.

Sentry Logs records a structured completion or failure for each non-health API request with its route template, method, status, duration, and request ID. Handled AI failures also emit a static `agent.run.failed` log with the agent, operation, and failure class. The log hook rejects other messages and removes all unapproved attributes; ordinary application log text is not forwarded.

What is not sent as an issue: 4xx responses, validation errors, and missing optional configuration. Request completion logs still include 4xx status codes. The `app.request` access logger is ignored because the structured log covers requests. Default PII, request bodies, query strings, cookies, local variables, and all headers except a small allowlist are dropped. URLs use the route template (`/sign/{token}`), and `before_send` redacts bearer tokens, credentials in URLs, secret-looking query values, email addresses, and secret-named keys in context.

Profiling and Sentry metrics are off. The API is limited to `MemoryMax=180M` on a 1 vCPU / 1 GB host. Pending events and logs are flushed on shutdown with a 2-second limit.

## Discord bot (`discord-bot-utility`)

The deployed bot has its own repository, `gobitsnbytes/bitsnbytes-discord-utility`. The tracked `apps/bot` copy in Motherboard does not by itself establish what runs in that deployment; verify the separate repository and its deployment before claiming bot rollout.

`apps/bot/lib/observability.js` initializes `@sentry/node` before the Discord client, command modules, jobs, and web server are loaded. A blank `SENTRY_DSN` disables reporting without changing startup behavior.

| Variable | Default | Notes |
| --- | --- | --- |
| `SENTRY_DSN` | blank (disabled) | Secret. `/opt/bits-bytes-bot/.env` on the VPS, ignored `apps/bot/.env` locally. |
| `SENTRY_ENVIRONMENT` | `NODE_ENV`, then `development` | Set this explicitly in production. |
| `SENTRY_TRACES_SAMPLE_RATE` | 0 | Keep low because the bot and API share a small VPS. |
| `SENTRY_RELEASE` | `bnb-bot@<package version>+<sha12>` | `GIT_SHA` or `GITHUB_SHA` supplies the optional revision. |

The bot reports command and Discord event failures through its logger, swallowed exceptions passed to `console.error`, scheduled-job failures, Express route rejections, HTTP listener errors, Discord client and shard errors, login failures, unhandled rejections, and uncaught exceptions. The same `Error` object is captured once even if it crosses more than one boundary. Fatal handlers and normal shutdown flush for at most two seconds.

Sentry Logs also receives static bot boot and command start/completion/failure events, plus severity-only events for the bot's info, warning, error, and success logger calls. Command names are limited to the Discord command slug format. Log messages, interaction data, users, and free-form logger details are rejected by `beforeSendLog`.

The weekly network brief sends Sentry Cron check-ins under `bot-weekly-brief` using its Monday schedule. Delivered and already-claimed runs finish `ok`; missing delivery channels and caught job exceptions finish `error`. Check-ins contain only the monitor slug, status, and SDK check-in ID.

Expected failures stay out of Sentry: disabled DMs, missing optional integrations, validation or permission failures, routine 4xx responses, and fallback warnings. Default PII, request bodies, query strings, cookies, local variables, users, and HTTP headers are dropped. The final scrubber also redacts bearer tokens, credentials in URLs, secret-looking query values, email addresses, and secret-named context fields.

The Sentry agent plugin is separate from API event reporting. Installing the plugin gives coding agents access to Sentry; it does not configure the running application.

The VPS API `.env` has `SENTRY_DSN` configured. A local SDK verification exception was sent on 2026-09-23 with event ID `706fec2b776a4211b75e5c9d60858c1c`. A direct ingest test to the frontend project returned event ID `a1777cf78a3c400e9ae9998cb063d07e`. These confirm network ingestion, not deployed application coverage. Verify one controlled exception from each running service after deployment.

The backend host had 956 MiB RAM, about 417 MiB available, and 562 MiB of swap in use when checked on 2026-09-23. PostgreSQL, API, bot, mail services, and telemetry share that host. A Dovecot `imap-login` assertion and an authentication worker failure appeared in the host journal; investigate the mail stack before attributing these events to Motherboard API.
