# Motherboard Cal.com routing design

Date: 2026-09-16

## Goal

Replace Chrono v2's duplicated scheduler, Discord voice-channel lifecycle, and meeting email system with a thin routing layer over individual Cal.com accounts.

Motherboard will decide which host should receive a booking. Cal.com will remain responsible for each host's availability, booking record, Google Meet creation, invitation email, reschedule email, cancellation email, and calendar event.

The result should provide the useful parts of Cal.com's Teams plan without claiming to unlock paid Cal.com features. We are building our own routing and administration layer around public and individually authorized Cal.com APIs.

## Constraints confirmed from Cal.com

- The free individual plan supports unlimited event types, calendars, meetings, and standard notifications.
- Native round-robin, collective and managed event types, routing forms, shared availability, and team analytics are paid Teams features.
- API v2 exposes individual event types, slots, bookings, rescheduling, cancellation, conferencing connections, and webhooks.
- Google Meet can be used as an event-type location after the host connects Google Calendar and Google Meet in Cal.com.
- Cal.com can send recording and transcription webhooks for Cal Video. It does not provide Google Meet transcripts. Google Meet transcription requires an eligible Google Workspace account and a separate Google integration.

References:

- https://cal.com/pricing
- https://cal.com/docs/api-reference/v2/introduction
- https://cal.com/docs/api-reference/v2/slots/get-available-time-slots-for-an-event-type
- https://cal.com/docs/api-reference/v2/bookings/create-a-booking
- https://cal.com/docs/developing/guides/automation/webhooks
- https://cal.com/docs/api-reference/v2/conferencing/connect-your-conferencing-application

## Approaches considered

### Buy Cal.com Teams

This is the cleanest operational option. Cal.com would own routing, team event types, and analytics. It is not currently affordable, so it is not the chosen implementation.

### Self-host Cal.com

Self-hosting could expose more of Cal.com's open-source team model, but it adds another production application, database, upgrade path, mail system, and Google OAuth configuration. This is too much operational weight for the immediate need.

### Motherboard routing over individual Cal.com accounts

This is the selected approach. Each host keeps an individual Cal.com account and event type. Motherboard aggregates availability and selects a host. The final booking is created against the selected host's Cal.com event type, so Cal.com creates the Google Meet link and sends all attendee notifications.

## Ownership boundaries

Cal.com is authoritative for:

- event type configuration;
- host availability and connected calendars;
- bookings and booking status;
- Google Meet links;
- attendee invitations, updates, and cancellations;
- the calendar event stored in Google Calendar.

Motherboard is authoritative for:

- host membership and eligibility;
- routing pools, weights, priority, and capacity limits;
- routing decisions and their audit trail;
- the local read model used by dashboards and reporting;
- webhook processing state;
- links from forms or internal workflows to routing pools;
- optional transcript ingestion from a future Google Workspace integration.

Discord has no role in booking, conferencing, reminders, attendance, or transcription.

## Host onboarding

The first version uses an individual Cal.com API key for each host because a verified Cal.com OAuth client is not currently available. Cal.com recommends OAuth for integrations, so the credential interface will be provider-neutral and replaceable when an OAuth client is approved.

Each host must:

1. create or use an individual Cal.com account;
2. connect the Google Calendar that should block availability;
3. connect Google Meet and set it as the location on the chosen event type;
4. create a dedicated Cal.com API key;
5. enter the API key and event type in Motherboard;
6. pass a connection test before becoming routable.

The API key is encrypted with the existing `EncryptedString` SQLAlchemy type. It is never returned by an API response or written to logs. A host can revoke or replace it at any time.

## Data model

### `calendar_connections`

- `id`
- `user_id`
- `provider`, fixed to `calcom` in this release
- `cal_user_id`
- `cal_username`
- `api_key`, encrypted
- `status`: `pending`, `active`, `invalid`, or `revoked`
- `last_verified_at`
- `last_error_code`
- timestamps

One active Cal.com connection is allowed per Motherboard user.

### `routing_pools`

- `id`
- `name`
- `slug`, unique public identifier
- `description`
- `algorithm`: `round_robin`, `weighted_round_robin`, or `priority`
- `active`
- `created_by`
- timestamps

### `routing_pool_members`

- `pool_id`
- `calendar_connection_id`
- `event_type_id`
- `event_type_slug`
- `weight`, default `1`
- `priority`, default `100`
- `daily_booking_limit`, nullable
- `active`
- `last_assigned_at`

The `(pool_id, calendar_connection_id, event_type_id)` tuple is unique.

### `calendar_bookings`

This replaces Cal.com-specific behavior currently mixed into `BotMeeting`.

- `id`
- `provider`, fixed to `calcom`
- `provider_booking_uid`, unique
- `provider_booking_id`, nullable
- `routing_pool_id`
- `routing_pool_member_id`
- `event_type_id`
- `host_user_id`
- attendee name, email, timezone, and guest emails
- `start_at` and `end_at` as timezone-aware timestamps
- `status`
- `meeting_url`
- `rescheduled_from_uid` and `rescheduled_to_uid`
- `provider_payload`, JSON for diagnostics
- timestamps

Existing meetings remain readable during migration. New routed bookings use `calendar_bookings`. No new booking is written to the bot SQLite database.

### `calendar_webhook_events`

- `id`
- `connection_id`
- `event_key`, unique
- `trigger`
- `booking_uid`
- `payload`
- `received_at`
- `processed_at`
- `status`: `received`, `processed`, or `failed`
- bounded error details and attempt count

The event key is a SHA-256 digest of the webhook version, trigger, booking UID, and provider creation timestamp. A unique constraint makes duplicate webhook delivery harmless.

### `routing_decisions`

- request id / idempotency key, unique
- routing pool
- requested slot and duration
- candidate snapshot
- selected member
- outcome and reason
- resulting booking UID
- timestamp

This table explains why a host was selected and prevents two retries from creating two bookings.

## Routing flow

### Availability

1. The client requests slots for a routing pool, date range, timezone, and duration.
2. Motherboard loads active pool members.
3. It requests `GET /v2/slots` for each member's individual event type using `format=range`.
4. It normalizes slots to UTC and builds a map from start time to eligible members.
5. It applies local capacity limits and returns only times with at least one eligible host.
6. Responses are cached briefly. The booking operation always checks Cal.com again before creating the booking.

Per-host failures do not fail the whole pool. An invalid credential removes that host from the response and records a connection health error.

### Host selection

The default algorithm is least-recently-assigned round robin among hosts who still expose the selected slot. Weighted pools expand the comparison using completed assignment counts over a rolling window. Priority pools select the lowest numeric priority first and round-robin within equal priority.

Selection runs inside a database transaction with a lock on the pool. This prevents concurrent requests from choosing the same host when another eligible host is available.

### Booking

1. The client submits the chosen slot, attendee details, and an `Idempotency-Key`.
2. Motherboard returns the existing result if that key already completed.
3. It refreshes availability for candidate hosts.
4. It selects one host and records the pending routing decision.
5. It calls `POST /v2/bookings` using that host's individual event type. The requested location is `google-meet`.
6. Cal.com creates the booking, Google Meet conference, calendar event, and attendee email.
7. Motherboard stores the booking UID and returns Cal.com's confirmation data.

Motherboard does not generate an ICS file or send an invitation email.

If Cal.com times out after accepting a booking, the routing decision stays `unknown`. A reconciliation lookup by booking metadata resolves it before any retry is allowed to create another booking.

### Reschedule and cancellation

Motherboard forwards reschedules to `POST /v2/bookings/{bookingUid}/reschedule` and cancellations to `POST /v2/bookings/{bookingUid}/cancel`.

The local read model changes only after Cal.com accepts the command or a webhook confirms it. Cal.com sends attendee updates. Motherboard sends no parallel email.

## Webhook processing

Each host connection has a Cal.com webhook with a distinct secret and a Motherboard callback identifier. The callback verifies `x-cal-signature-256` against the raw request body before parsing JSON.

Supported triggers in the first release:

- `BOOKING_CREATED`
- `BOOKING_RESCHEDULED`
- `BOOKING_CANCELLED`
- `BOOKING_REJECTED`
- `BOOKING_NO_SHOW_UPDATED`
- `MEETING_STARTED`
- `MEETING_ENDED`
- `BOOKING_LOCATION_UPDATED`

The endpoint stores the event before processing it and acknowledges duplicates. Processing updates `calendar_bookings`; it does not call Cal.com, send mail, or post to Discord. This prevents webhook loops.

A reconciliation job runs at a low frequency to compare recent local booking UIDs with Cal.com. It may repair the local read model, but it cannot create bookings or notify attendees.

## API surface

Authenticated administration:

- `POST /api/calendar/connections/calcom`
- `POST /api/calendar/connections/{id}/verify`
- `DELETE /api/calendar/connections/{id}`
- `GET|POST|PATCH /api/calendar/routing-pools`
- `POST|DELETE /api/calendar/routing-pools/{id}/members`
- `GET /api/calendar/bookings`

Public booking:

- `GET /api/calendar/public/{poolSlug}/slots`
- `POST /api/calendar/public/{poolSlug}/book`
- `POST /api/calendar/public/bookings/{uid}/reschedule`
- `POST /api/calendar/public/bookings/{uid}/cancel`

Provider callback:

- `POST /api/calendar/webhooks/calcom/{connectionId}`

Public mutation endpoints use a signed booking-management token, rate limits, strict Pydantic schemas, and required idempotency keys. They never expose Cal.com credentials.

## UI

The Meetings area becomes a calendar operations screen with four sections:

- booking overview;
- routing pools and members;
- individual Cal.com connection health;
- public booking links and routing audit.

The current Discord VC controls, recording controls, bot reminder settings, manual SMTP settings, and raw availability JSON editor are removed from the active interface.

The public booking page shows the routing pool rather than a specific host. It asks for a date, slot, name, email, timezone, and any configured intake fields. It does not reveal the selected host until Cal.com confirms the booking.

## Transcription

Transcription is not part of the first Cal.com/GMeet routing release because Cal.com does not supply Google Meet transcripts.

The booking model keeps provider-neutral artifact fields so a later Google Workspace integration can attach a transcript or recording by conference record. Until that integration exists, the UI must say transcription is unavailable for Google Meet rather than claiming it is automatic.

## Migration and removal

1. Keep the legacy Cal.com poller disabled.
2. Add the new tables and unique constraints with an expand-only Alembic migration.
3. Deploy connection onboarding and health checks.
4. Deploy pool administration and aggregated slots.
5. Deploy idempotent booking, webhook ingestion, reschedule, and cancellation.
6. Move the public and dashboard booking surfaces to `/api/calendar`.
7. Remove runtime calls to Discord VC creation, bot meeting reminders, bot meeting mail, and local meeting SQLite writes.
8. Preserve old meeting and transcript records as read-only history.

The migration does not delete existing meetings, transcripts, recordings, or bot data.

## Failure handling

- Invalid host credentials disable only that host and show an actionable admin error.
- Cal.com rate limits return a retryable response and do not advance the routing cursor.
- A stale slot triggers one candidate refresh; if no host remains, the client receives a conflict and must choose another time.
- Duplicate form submissions return the original booking.
- Duplicate webhooks return success without repeating work.
- Cal.com outages never fall back to local meeting creation or SMTP.
- Secrets and full provider payloads are never logged.

## Tests and acceptance criteria

The release is complete when:

- two individual Cal.com accounts can join one Motherboard routing pool;
- aggregated slots reflect each account's real Cal.com availability;
- repeated booking requests with one idempotency key create exactly one Cal.com booking;
- round-robin selection distributes sequential bookings across available hosts;
- a concurrent booking test cannot create duplicate bookings or corrupt the routing cursor;
- every new booking uses Google Meet and returns the Cal-generated meeting URL;
- Cal.com, not Motherboard or the bot, sends attendee booking emails;
- create, reschedule, cancel, and duplicate webhook fixtures converge to the correct local state;
- invalid webhook signatures are rejected before payload processing;
- the legacy poller, Discord VC creation, and meeting SMTP paths are unreachable from the new calendar UI;
- production logs show no repeating Cal.com import loop and no implicit CC/BCC recipients.

## Deliberate exclusions

- bypassing or modifying Cal.com's paid Teams product;
- collective bookings requiring several hosts at once;
- attribute-based CRM routing;
- Cal Video recordings;
- automatic Google Meet transcription;
- a second scheduling provider.

These can be added after the individual-account routing path is stable.
