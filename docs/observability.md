# Sentry error reporting

The web app uses `@sentry/nextjs` in browser, Node.js, and Edge runtimes. Set `NEXT_PUBLIC_SENTRY_DSN` and `SENTRY_DSN` in the web deployment environment and in an ignored local `apps/web/.env.local` for local testing. `NEXT_PUBLIC_SENTRY_DSN` is embedded at build time. Set `SENTRY_PROJECT` and a secret `SENTRY_AUTH_TOKEN` during production builds to upload source maps; the organization is `gobitsnbytes-foundation`. The SDK samples 10% of traces and leaves default PII collection off. The bot uses `@sentry/node`; set `SENTRY_DSN` in `/opt/bits-bytes-bot/.env` to capture handled bot errors through its logger.

The FastAPI service can send unhandled errors to Sentry. Set `SENTRY_DSN` in the API service environment to enable it. Keep the DSN in the deployment secret store, not in Git. With the variable unset, the SDK does not initialize.

The API uses `bnb-api@<APP_VERSION>` as its Sentry release. Default PII collection, request body capture, tracing, and profiling are disabled. This fits the small `bnb-backend` host and limits event volume. Request IDs remain in the API response header and structured server logs for correlation.

The Sentry agent plugin is separate from API event reporting. Installing the plugin gives coding agents access to Sentry; it does not configure the running application.

The VPS API `.env` has `SENTRY_DSN` configured. A local SDK verification exception was sent on 2026-09-23 with event ID `706fec2b776a4211b75e5c9d60858c1c`. A direct ingest test to the frontend project returned event ID `a1777cf78a3c400e9ae9998cb063d07e`. These confirm network ingestion, not deployed application coverage. Verify one controlled exception from each running service after deployment.

The backend host had 956 MiB RAM, about 417 MiB available, and 562 MiB of swap in use when checked on 2026-09-23. PostgreSQL, API, bot, mail services, and telemetry share that host. A Dovecot `imap-login` assertion and an authentication worker failure appeared in the host journal; investigate the mail stack before attributing these events to Motherboard API.
