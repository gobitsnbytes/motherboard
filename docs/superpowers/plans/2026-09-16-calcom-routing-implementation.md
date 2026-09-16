# Cal.com routing implementation plan

Date: 2026-09-16
Design: `docs/superpowers/specs/2026-09-16-calcom-routing-design.md`

## Objective

Replace Chrono v2's active meeting creation path with a Motherboard routing layer over individual Cal.com event types. Cal.com remains the source of truth for availability, bookings, Google Meet links, calendar events, and attendee notifications.

## Non-negotiable invariants

- No new booking path sends SMTP, creates Discord channels, writes bot SQLite meeting rows, or generates ICS files.
- Every booking mutation is idempotent before the external Cal.com call.
- Cal.com API keys and webhook secrets are encrypted at rest and never returned or logged.
- Webhook signatures are checked against the raw body before JSON parsing.
- Old meeting records remain readable; the migration is expand-only.

## Phase 1 — persistence and provider adapter

1. Add the six approved calendar tables and constraints to `app/db/models.py`.
2. Add an expand-only Alembic migration from the current merged head.
3. Add strict Pydantic request/response schemas in `app/schemas/calendar.py`.
4. Add one `httpx` Cal.com adapter in `app/services/calcom.py` with endpoint-specific API versions for connection verification, slots, booking, reschedule, cancellation, and webhook registration.
5. Cover request construction, provider error redaction, encryption, and model constraints with focused tests.

Acceptance:

- SQLite test metadata and PostgreSQL migration both represent the same constraints.
- Cal.com authorization and API-version headers are correct per endpoint.
- No credential appears in exceptions or API responses.

## Phase 2 — routing and booking lifecycle

1. Add a calendar service that aggregates slots and selects eligible members using least-recently-assigned round robin.
2. Lock the routing pool during selection on PostgreSQL; retain SQLite compatibility for tests.
3. Require an `Idempotency-Key` for public create, reschedule, and cancel operations.
4. Persist the routing decision before contacting Cal.com and return the stored result for completed retries.
5. Treat uncertain provider outcomes as `unknown`; never issue a blind second create.

Acceptance:

- Sequential assignments rotate across available hosts.
- Repeating one key creates one provider booking.
- Concurrent requests do not corrupt routing state.
- Google Meet is requested with Cal.com's `google_meet` location type.

## Phase 3 — API and webhook ingestion

1. Add authenticated connection and routing-pool administration endpoints.
2. Add public slot, booking, reschedule, and cancel endpoints.
3. Add the raw-body Cal.com webhook endpoint with HMAC verification and a unique event digest.
4. Process booking lifecycle webhooks only into the local read model; never call Cal.com, Discord, or SMTP from webhook handling.
5. Register the router in `app/main.py` and add the required IAM permissions to the existing seed/constants path.

Acceptance:

- Invalid signatures fail before payload processing.
- Duplicate webhooks return success without repeating state changes.
- Public endpoints expose no provider credentials or private provider payload.
- Administrative operations require the existing IAM policy checks.

## Phase 4 — user interface cutover

1. Replace active Chrono v2 scheduling controls with routing pools, host connection health, booking history, and public booking links.
2. Build a public pool booking flow backed only by `/api/calendar`.
3. Remove Discord VC, bot reminder, SMTP, and raw availability controls from the active calendar UI.
4. Keep old meetings and transcripts visible as read-only history.

Acceptance:

- The UI cannot invoke the legacy Discord/SMTP meeting creation path.
- A visitor can choose a pooled slot and receive the Cal.com booking confirmation.
- Admins can onboard a host and manage pool membership without exposing the API key after submission.

## Phase 5 — hardening and release

1. Run focused and full backend/frontend tests, type checks, and lint.
2. Review the diff for security, over-engineering, unreachable legacy runtime calls, and accidental secret logging.
3. Update `MEMORY.md` without overwriting unrelated user edits.
4. Commit atomically, push `main`, merge to `prod`, and let CI deploy.
5. Verify service health and confirm production logs contain no calendar import loop, booking SMTP, or implicit CC/BCC traffic.

Rollback:

- Revert the application commits while leaving the additive tables in place.
- Do not downgrade or delete calendar data during an incident.
- Disable the new `/api/calendar` UI entry point; do not re-enable the Cal.com poller or Discord meeting creation.

## Explicitly deferred

- Weighted and priority routing UI beyond storing the approved fields.
- Google Meet transcript ingestion.
- Cal.com OAuth migration.
- Multi-provider scheduling.
- Deletion of legacy meeting data or tables.
