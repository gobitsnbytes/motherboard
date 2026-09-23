# API error reporting

The FastAPI service can send unhandled errors to Sentry. Set `SENTRY_DSN` in the API service environment to enable it. Keep the DSN in the deployment secret store, not in Git. With the variable unset, the SDK does not initialize.

The API uses `bnb-api@<APP_VERSION>` as its Sentry release. Default PII collection, request body capture, tracing, and profiling are disabled. This fits the small `bnb-backend` host and limits event volume. Request IDs remain in the API response header and structured server logs for correlation.

The Sentry agent plugin is separate from API event reporting. Installing the plugin gives coding agents access to Sentry; it does not configure the running application.

The VPS API `.env` has `SENTRY_DSN` configured. A local SDK verification exception was sent on 2026-09-23 with event ID `706fec2b776a4211b75e5c9d60858c1c`. This confirms that the SDK can flush an error envelope; production API reporting still requires the code to be deployed and verified in Sentry.

The backend host had 956 MiB RAM, about 417 MiB available, and 562 MiB of swap in use when checked on 2026-09-23. PostgreSQL, API, bot, mail services, and telemetry share that host. A Dovecot `imap-login` assertion and an authentication worker failure appeared in the host journal; investigate the mail stack before attributing these events to Motherboard API.
