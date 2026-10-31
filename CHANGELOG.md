# Changelog

## 1.0.0 — 2026-10-31

First stable release. No beta or alpha labels remain.

- Web: every page now reports a failed request as an error with a reason (no access, server slow, server unreachable) instead of an empty list. One shared client handles retries on reads, a 30 second timeout and FastAPI validation errors.
- Web: sign-in failures land on the login page with a specific message instead of a dead-end error screen.
- API: database connections are capped and time-boxed for the 1 GB host, and large JSON responses are compressed.
- Tests: a contract test fails the build when the web app calls an API route that does not exist.

## 0.86.0 beta 1 — 2026-09-12

- Added the public form builder and public response intake workflow.
- Made form submission retries idempotent and cleaned up duplicate TechFest responses.
- Improved response review with accurate counts, latest-response context, and accessible filter feedback.

## 0.85.5 beta — 2026-09-09

This is the first explicitly versioned beta release of Motherboard.

- Established `0.85.5-beta` as the canonical application release identifier.
- Updated web, UI package, API package, OpenAPI, health, and finance metadata.
- Replaced the old `v0.2.0` product label in the sidebar, login surface, settings fallback, and diagnostics panel.
- Includes the current UI overhaul checkpoints and IAM regression gate.

This release is a beta checkpoint. The full release process and 1.0 milestone remain future work.
