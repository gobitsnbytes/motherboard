# Dyslexic — Sponsorship & Outreach Module

**Status:** Approved design, ready for implementation planning
**Date:** 2026-08-03
**Module owner:** Outreach track

---

## 1. What Dyslexic is

An internal sponsorship and outreach workspace inside Motherboard. Volunteers add companies,
the system researches them with AI, volunteers add contacts and generate personalised sponsor
emails, then log what they sent and what came back. The point is that a dozen volunteers can
work the same sponsor pipeline at once without emailing the same person twice or losing track
of who owes a follow-up.

Dyslexic **does not send email.** It generates a draft, the volunteer copies it into Gmail and
sends it there, then comes back and clicks "I've Sent Email".

### Success criteria

- Two volunteers cannot both send an initial email to the same contact. The second attempt is
  refused by the database, not by convention.
- Adding a company takes two fields: name and website. Everything else is researched.
- A volunteer's contribution numbers are never typed in by hand. They fall out of the records.
- Every company has a readable history: who did what, when.
- Nothing about the module looks or behaves like it was bolted on afterwards.

### Non-goals

- Sending, receiving, or syncing email. No SMTP, no Gmail API, no IMAP.
- Discord DM reminders. Follow-ups are surfaced in-app only.
- CRM features beyond the sponsorship loop: no deal amounts, no contracts, no invoicing.
  Finance already owns money.
- A separate permission surface. See §3.

---

## 2. How it fits the existing platform

Dyslexic is a **core module**, built the way Meetings, IAM and Finance are built. Not a plugin:
the Plugin SDK has no path into Alembic for its tables, and plugin UI is a client-only
`dynamic()` import reaching outside `apps/web`, which rules out server components and the shared
layout. `plugins/sample_plugin` is the SDK's only consumer and it is a hello-world.

| Concern | Existing mechanism Dyslexic reuses | Reference |
| --- | --- | --- |
| Identity | NextAuth v5 Discord OAuth, `session.user.internalUserId` | `apps/web/lib/auth.ts` |
| Browser → API | catch-all proxy, HMAC-signed internal headers | `apps/web/app/api/[...path]/route.ts` |
| API auth | `get_current_user` → `ResolvedPrincipal` | `apps/api/app/dependencies.py:59` |
| Audit trail | `write_audit_entry` (non-committing, caller owns txn) | `apps/api/app/iam/audit.py` |
| Cross-node events | Redis pub/sub `event_bus.publish` | `apps/api/app/events/bus.py` |
| Schema migration | Alembic, auto-upgraded in lifespan | `apps/api/app/main.py:52` |
| AI | `google-genai`, key + model in settings | `apps/api/app/config.py:32` |
| UI kit | `@bnb/ui` neobrutalist components | `packages/ui/src/index.ts` |
| Shell & nav | `DashboardShell`, `navItems` array | `apps/web/components/dashboard/Sidebar.tsx:35` |

New plumbing is limited to two things: the SSE endpoint and hub (§8), and a streaming branch in
the Next proxy (§8.2). Everything else is composition of what exists.

### Files added

```
apps/api/app/routers/dyslexic.py          — all routes
apps/api/app/schemas/dyslexic.py          — Pydantic v2 request/response models
apps/api/app/dyslexic/__init__.py
apps/api/app/dyslexic/research.py         — grounded company research
apps/api/app/dyslexic/emails.py           — draft generation
apps/api/app/dyslexic/service.py          — transactional workflow operations
apps/api/app/dyslexic/stats.py            — leaderboard / dashboard aggregates
apps/api/app/events/sse.py                — SseHub, shared, not Dyslexic-specific
apps/api/alembic/versions/<rev>_add_dyslexic_tables.py
apps/api/tests/test_dyslexic_*.py

apps/web/app/dashboard/dyslexic/page.tsx            — dashboard
apps/web/app/dashboard/dyslexic/companies/page.tsx
apps/web/app/dashboard/dyslexic/companies/[id]/page.tsx
apps/web/app/dashboard/dyslexic/contacts/page.tsx
apps/web/app/dashboard/dyslexic/leaderboard/page.tsx
apps/web/components/dyslexic/*.tsx
apps/web/lib/dyslexic.ts                  — fetch wrappers
apps/web/hooks/useDyslexicStream.ts
```

### Files modified

```
apps/api/app/db/models.py                 — six new models
apps/api/app/main.py                      — include dyslexic router
apps/api/app/config.py                    — DYSLEXIC_GEMINI_MODEL setting
apps/web/app/api/[...path]/route.ts       — pass through text/event-stream unbuffered
apps/web/components/dashboard/Sidebar.tsx — one nav entry
deploy/api/nginx.conf                     — proxy_buffering off on the stream path
.env.example                              — DYSLEXIC_GEMINI_MODEL
```

---

## 3. Access model

**Any logged-in Motherboard user has full access to Dyslexic.** No `dyslexic.*` permission keys
are registered, nothing is added to `CORE_PERMISSIONS`, no grants are required. Every route
depends on `CurrentUserDep` and nothing further. The sidebar entry is unconditional.

This is a deliberate decision: outreach is volunteer-driven and gating it would slow down the
people it is meant to help. Two design choices carry the safety that permissions would otherwise
have provided:

- **Archive, never delete.** Companies and contacts have `is_archived`. No `DELETE` route is
  exposed for either. A misclick hides a record; it does not destroy a term of outreach history.
- **Everything is attributed.** Every mutation writes a `dyslexic_events` row naming the actor,
  and an `audit_log` entry. Open access with a complete trail is a fair trade. Open access with
  no trail is not.

Super admins already bypass all checks via `ResolvedPrincipal.is_super_admin`; nothing special is
needed for them.

---

## 4. Data model

Six tables in `apps/api/app/db/models.py`, one Alembic revision. House conventions throughout:
`uuid.UUID` primary keys defaulting to `uuid.uuid4`, `DateTime(timezone=True)` with
`server_default=func.now()`, `onupdate=func.now()` on `updated_at`, JSON blobs on
`metadata_json`, and `ondelete="SET NULL"` on every FK to `users.id` so deactivating a volunteer
never erases their outreach record.

Tables are prefixed `dyslexic_` to match the audit namespace and because `companies` / `contacts`
are names a future module will plausibly want.

### 4.1 `dyslexic_companies`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `name` | String(200) | required |
| `website` | String(500) | nullable |
| `normalized_domain` | String(255) | **unique**, indexed, nullable. Derived from `website`: lowercase, strip scheme, strip `www.`, strip path and trailing slash. Null when no website given. |
| `stage` | String(30) | default `research`, see §5.1 |
| `research_status` | String(20) | default `pending` — `pending` \| `running` \| `complete` \| `failed` |
| `research_json` | JSON | default `{}`, see §7.1 for shape |
| `research_raw` | Text | nullable, model output kept when parsing fails |
| `research_error` | Text | nullable |
| `research_generated_at` | DateTime | nullable |
| `research_model` | String(60) | nullable, which model produced it |
| `notes` | Text | nullable, free-text volunteer notes |
| `added_by` | FK users.id SET NULL | indexed |
| `fork_id` | FK forks.id SET NULL | nullable — which city fork is chasing this lead |
| `is_archived` | Boolean | default false |
| `created_at`, `updated_at` | DateTime | |

Indexes: `ix_dyslexic_companies_stage`, `ix_dyslexic_companies_added_by`,
`ix_dyslexic_companies_normalized_domain` (unique).

`stage` is stored rather than derived so the pipeline view can filter and sort without joining
across the whole outreach history.

### 4.2 `dyslexic_contacts`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `company_id` | FK companies CASCADE | indexed |
| `name` | String(150) | required |
| `role` | String(150) | nullable |
| `email` | String(255) | nullable, **stored lowercased** |
| `linkedin_url` | String(500) | nullable |
| `notes` | Text | nullable |
| `status` | String(30) | default `new`, see §5.2 |
| `contacted_by` | FK users.id SET NULL | set once at first send, never overwritten |
| `contacted_at` | DateTime | nullable |
| `claimed_by` | FK users.id SET NULL | soft draft claim |
| `claimed_at` | DateTime | nullable |
| `claim_expires_at` | DateTime | nullable, indexed |
| `added_by` | FK users.id SET NULL | indexed |
| `is_archived` | Boolean | default false |
| `created_at`, `updated_at` | DateTime | |

Constraint: `UniqueConstraint("company_id", "email", name="uq_dyslexic_contact_company_email")`.
Postgres treats NULLs as distinct, so several contacts without an email at one company are fine,
while the same address twice is refused.

The same email at a *different* company is allowed — people change jobs, and one person can be
the right contact at two sponsors. `POST` returns a non-blocking `duplicate_warning` naming the
other company so the volunteer knows.

### 4.3 `dyslexic_emails`

Every generated draft, kept whether or not it was ever used.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `contact_id` | FK contacts CASCADE | indexed |
| `company_id` | FK companies CASCADE | denormalised for company-level queries |
| `kind` | String(20) | `initial` \| `follow_up` |
| `subject` | Text | |
| `body` | Text | |
| `tone` | String(30) | nullable, requested tone |
| `extra_context` | Text | nullable, what the volunteer asked for |
| `model` | String(60) | which model generated it |
| `generated_by` | FK users.id SET NULL | indexed |
| `created_at` | DateTime | |

### 4.4 `dyslexic_outreach`

The record of an actual send — one row per "I've Sent Email" click.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `contact_id` | FK contacts CASCADE | indexed |
| `company_id` | FK companies CASCADE | indexed |
| `email_id` | FK emails SET NULL | nullable — sending without generating is allowed |
| `kind` | String(20) | `initial` \| `follow_up` |
| `sent_by` | FK users.id SET NULL | indexed |
| `sent_at` | DateTime | |
| `outcome` | String(30) | nullable until the day-3 update, see §5.3 |
| `outcome_at` | DateTime | nullable |
| `outcome_by` | FK users.id SET NULL | nullable |
| `outcome_note` | Text | nullable |

**The duplicate guard is a partial unique index:**

```python
Index(
    "uq_dyslexic_outreach_initial_per_contact",
    "contact_id",
    unique=True,
    postgresql_where=text("kind = 'initial'"),
    sqlite_where=text("kind = 'initial'"),
)
```

Both Postgres and the aiosqlite test database support partial indexes, so the constraint is
enforced identically in tests and production. Follow-ups are unconstrained — a contact can be
chased more than once.

### 4.5 `dyslexic_follow_ups`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `outreach_id` | FK outreach CASCADE | indexed |
| `contact_id` | FK contacts CASCADE | denormalised |
| `company_id` | FK companies CASCADE | denormalised |
| `assigned_to` | FK users.id SET NULL | defaults to the sender |
| `due_at` | DateTime | sent_at + 3 days |
| `status` | String(20) | default `pending` — `pending` \| `done` \| `cancelled` |
| `resolved_at` | DateTime | nullable |
| `resolved_by` | FK users.id SET NULL | nullable |
| `created_at` | DateTime | |

Composite index `ix_dyslexic_follow_ups_assignee_due` on `(assigned_to, status, due_at)` — the
dashboard's "my follow-ups due" query hits it directly.

The three-day interval is a module constant `FOLLOW_UP_INTERVAL_DAYS = 3`, not a magic number
scattered through handlers.

### 4.6 `dyslexic_events`

The per-company timeline. Product data, indexed by company.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `company_id` | FK companies CASCADE | indexed |
| `contact_id` | FK contacts SET NULL | nullable |
| `actor_id` | FK users.id SET NULL | nullable — null for system-generated entries |
| `kind` | String(50) | see below |
| `summary` | String(300) | human-readable, rendered directly |
| `metadata_json` | JSON | default `{}` |
| `created_at` | DateTime | indexed |

Event kinds: `company.added`, `research.generated`, `research.failed`, `contact.added`,
`contact.updated`, `email.generated`, `email.sent`, `follow_up.sent`, `outcome.recorded`,
`stage.changed`, `note.added`, `company.archived`.

**Why not reuse `audit_log`?** It is a platform-wide forensic record, indexed on `action` and
`created_at`, with no index on `target_id`. A per-company product feed is a different query shape
with a different reader. Both are written: `dyslexic_events` for the UI timeline, `audit_log` for
platform forensics, in the same transaction. The duplication is two inserts and it keeps the
immutable audit trail from becoming a UI dependency.

### 4.7 No statistics table

Volunteer analytics are aggregate queries over the tables above (§9). Denormalised counters drift
from reality the first time a transaction is rolled back or a record is corrected. At this org's
scale — dozens of volunteers, hundreds of companies — the aggregates are instant. If they ever
stop being, materialise then, with evidence.

---

## 5. State machines

### 5.1 Company stage

```
research → contacts_added → email_generated → email_sent → follow_up
         → replied → meeting → negotiation → sponsored
                                           → rejected
```

Transitions are **monotonic**: a stage only advances. `email_sent` on a second contact at a
company already at `meeting` does not pull it backwards. Implemented as an ordered list with an
index comparison in `service.py`; the automatic transitions are:

| Trigger | New stage (if further along) |
| --- | --- |
| company created | `research` |
| first contact added | `contacts_added` |
| first draft generated | `email_generated` |
| first send logged | `email_sent` |
| follow-up send logged | `follow_up` |
| outcome `replied` | `replied` |
| outcome `meeting_scheduled` | `meeting` |
| outcome `sponsored` | `sponsored` |
| outcome `rejected` | `rejected` |

`negotiation` has no automatic trigger — it is set manually via `PATCH /companies/{id}`, which is
also the escape hatch for correcting any stage. `sponsored` and `rejected` are terminal for
automatic transitions but remain manually editable. Every change writes a `stage.changed` event.

### 5.2 Contact status

`new → contacted → {no_reply | replied | meeting_scheduled | sponsored | rejected}`

Mirrors the latest recorded outcome on that contact. `bounced` is available as a manual status
for dead addresses; a bounced contact can be edited with a corrected email, which resets it to
`new` only if no outreach row exists.

### 5.3 Outreach outcome

Exactly the six from the requirement: `follow_up_sent`, `no_reply`, `replied`,
`meeting_scheduled`, `sponsored`, `rejected`.

**Invariant: a contact has at most one pending follow-up.** There are two ways a chase gets
logged — `POST /contacts/{id}/sent` with `kind="follow_up"`, and recording the outcome
`follow_up_sent` on an earlier outreach row — and without a rule they would each open a
follow-up and leave the contact with two. Both routes therefore call the same
`service.log_send()`, which always resolves any pending follow-up for that contact before
creating the new one. Recording `follow_up_sent` is defined as: resolve the current follow-up,
insert a new `dyslexic_outreach` row with `kind="follow_up"` attributed to whoever recorded it,
and open a fresh follow-up three days out. The two paths converge on identical state.

---

## 6. API

All routes under `/api/dyslexic`, in `apps/api/app/routers/dyslexic.py`, registered in
`create_app()`. All depend on `DbSession` and `CurrentUserDep`.

### 6.1 Dashboard and analytics

```
GET /api/dyslexic/stats
    → { companies, contacts, emails_sent, replies, follow_ups_due,
        my_follow_ups_due, sponsors_closed }

GET /api/dyslexic/activity?limit=20&offset=0
    → recent dyslexic_events across all companies, each with actor display_name and avatar

GET /api/dyslexic/leaderboard?period=all|30d
    → [ { user_id, display_name, avatar_url, companies_added, contacts_added,
          emails_sent, follow_ups_sent, replies_received, meetings_scheduled,
          sponsors_closed, score } ]
```

### 6.2 Companies

```
GET   /api/dyslexic/companies?stage=&q=&fork_id=&archived=false&limit=50&offset=0
POST  /api/dyslexic/companies          { name, website?, fork_id?, notes? }  → 201
GET   /api/dyslexic/companies/{id}     → company + contacts + research + timeline
PATCH /api/dyslexic/companies/{id}     { name?, website?, notes?, stage?, fork_id?, is_archived? }
POST  /api/dyslexic/companies/{id}/research      → 202
GET   /api/dyslexic/companies/{id}/timeline?limit=50
```

`POST /companies` normalises the website to a domain and looks it up. On collision it returns
**409** with the existing company's id and name in the body, so the UI can offer "open the
existing record" rather than a dead-end error. When no website is supplied there is no domain to
compare, so the check falls back to a case-insensitive exact match on `name` among non-archived
companies and returns the same 409. Creation queues research as a background task and returns
immediately with `research_status: "pending"`.

### 6.3 Contacts

```
GET    /api/dyslexic/contacts?company_id=&status=&q=&limit=&offset=
POST   /api/dyslexic/companies/{id}/contacts  { name, role?, email?, linkedin_url?, notes? } → 201
PATCH  /api/dyslexic/contacts/{id}            { name?, role?, email?, linkedin_url?, notes?,
                                                status?, is_archived? }
POST   /api/dyslexic/contacts/{id}/claim      → 200 | 409
DELETE /api/dyslexic/contacts/{id}/claim      → 204
```

`POST /claim` is an atomic conditional update:

```sql
UPDATE dyslexic_contacts
   SET claimed_by = :me, claimed_at = now(), claim_expires_at = now() + interval '30 minutes'
 WHERE id = :id
   AND (claimed_by IS NULL OR claimed_by = :me OR claim_expires_at < now())
```

Zero rows updated means someone else holds it — respond **409** with the holder's display name
and expiry. Claims expire on their own; there is no unlock button and no cleanup job. Re-claiming
your own contact extends the window, which is what happens when you regenerate a draft.

### 6.4 Emails and outreach

```
POST  /api/dyslexic/contacts/{id}/generate-email  { kind, tone?, extra_context? } → 201
GET   /api/dyslexic/contacts/{id}/emails
POST  /api/dyslexic/contacts/{id}/sent            { email_id?, kind }             → 201
PATCH /api/dyslexic/outreach/{id}/outcome         { outcome, note? }
```

`generate-email` takes or extends the claim before calling the model, so the claim is visible to
everyone else the moment drafting starts.

`POST /contacts/{id}/sent` is the critical path. One transaction:

1. `SELECT … FOR UPDATE` on the contact.
2. If `kind == "initial"` and `contacted_at` is already set → **409**, body names the volunteer
   and the date. The partial unique index is the backstop if two requests race past the check.
3. Insert `dyslexic_outreach`.
4. On initial: set `contacted_by`, `contacted_at`, `status = "contacted"`.
5. Advance `company.stage` if the new stage is further along.
6. Resolve any pending follow-up for this contact, then insert a new `dyslexic_follow_ups` due in
   three days, assigned to the sender — preserving the one-pending-follow-up-per-contact
   invariant from §5.3.
7. Insert `dyslexic_events` (`email.sent` or `follow_up.sent`) and `audit_log`.
8. Clear the claim.
9. Commit, **then** `event_bus.publish` — publishing before commit would announce a state that
   might roll back.

`PATCH /outreach/{id}/outcome` records the outcome, updates contact status and company stage, and
resolves the open follow-up. When the outcome is `follow_up_sent` it delegates to the same
`service.log_send()` used above, so a chase logged this way is indistinguishable from one logged
through `POST /sent`.

### 6.5 Follow-ups and stream

```
GET  /api/dyslexic/follow-ups?scope=mine|all&status=pending&overdue=true
POST /api/dyslexic/follow-ups/{id}/resolve   { note? }
GET  /api/dyslexic/stream                    → text/event-stream
```

### 6.6 Error conventions

Matching the rest of the API: `HTTPException` with a `detail` string, `404` for missing records,
`409` for state conflicts (duplicate domain, already contacted, claim held), `400` for invalid
input past Pydantic, `422` from Pydantic itself. Conflict responses carry structured context in
`detail` so the UI can render something actionable rather than a raw string.

---

## 7. AI integration

`google-genai` is already a dependency and `meetings.py:919` is the working reference for client
construction and response handling.

**Model.** A new setting `dyslexic_gemini_model`, `DYSLEXIC_GEMINI_MODEL`, defaulting to
`gemini-3.6-flash`. Deliberately separate from the existing `gemini_model` so Dyslexic does not
silently move the meeting-transcription pipeline onto a different model.

Gemini 3.6 has migration constraints that apply here: `temperature`, `top_p` and `top_k` are
ignored, `thinking_budget` is replaced by a `thinking_level` string, and `candidate_count` is
gone. Calls are written against 3.6 from the start rather than copied from the 2.5-era call in
`meetings.py`.

### 7.1 Company research

Triggered on company creation and by `POST /companies/{id}/research`, always as a FastAPI
`BackgroundTask`. `research_status` moves `pending → running → complete | failed`. Completion
publishes `dyslexic.research.completed` on the event bus, which reaches the browser over SSE.
Nothing in the request path waits on the model.

The call uses the **Google Search grounding tool**. Grounding and JSON response mode do not
combine cleanly, so the prompt demands a bare JSON object and the handler parses defensively —
stripping markdown fences the way `meetings.py` already does. Source URLs come from the
response's grounding metadata, not from the model's prose, which means the model cannot fabricate
a citation.

`research_json` shape:

```json
{
  "summary": "2-3 sentences on what the company does",
  "industry": "string",
  "size": "string, e.g. '200-500 employees'",
  "headquarters": "string",
  "products": ["string"],
  "sponsorship_angle": "why this company might sponsor a student tech community",
  "suggested_contact_roles": ["Head of Developer Relations", "Campus Marketing Lead"],
  "recent_news": ["string"],
  "confidence": "high | medium | low",
  "sources": [{ "title": "string", "url": "string" }]
}
```

On a parse failure the raw text is kept in `research_raw`, `research_status` becomes `failed`,
and `research_error` explains why. **Failed research never blocks the workflow** — the company is
fully usable, the panel shows what went wrong and offers Retry. Research is advisory, not a gate.

If `gemini_api_key` is unset, research is skipped with `research_status = "failed"` and a clear
message rather than a 500; the rest of the module works without AI.

### 7.2 Email generation

A second, ungrounded call. Input: the company's `research_json`, the contact's name and role, the
volunteer's requested tone and extra context, and bits&bytes framing pulled from `docs/design.md`
— lowercase **bits&bytes**, never "Bits & Bytes" or "B&B"; `GOBITSNBYTES FOUNDATION` only where a
legal entity name belongs. Output is `{ subject, body }`, persisted to `dyslexic_emails`.

Follow-up drafts additionally receive the prior email's subject and body and the number of days
since it went out, so the model writes a chase rather than a fresh pitch.

The draft is fully editable in a textarea before copying. What the volunteer copies is whatever is
in the box, not what the model returned.

---

## 8. Live collaboration

### 8.1 Server

`apps/api/app/events/sse.py` adds an `SseHub`: it subscribes once to the event bus for the
relevant event types and fans each payload out to a per-connection `asyncio.Queue`. Connections
register on open and deregister in a `finally`, so a dropped client cannot leak a queue.

`GET /api/dyslexic/stream` returns a `StreamingResponse` with media type `text/event-stream`,
yielding one SSE frame per event plus a `: heartbeat` comment every 20 seconds to hold the
connection through intermediate proxies.

Published event types: `dyslexic.company.created`, `dyslexic.company.updated`,
`dyslexic.research.completed`, `dyslexic.contact.created`, `dyslexic.contact.claimed`,
`dyslexic.contact.released`, `dyslexic.email.sent`, `dyslexic.outcome.recorded`,
`dyslexic.follow_up.created`, `dyslexic.follow_up.resolved`.

Payloads carry ids and a short summary, never full records. The client refetches the affected
list; the stream is a change notification, not a replication channel.

### 8.2 Proxy change (required)

`apps/web/app/api/[...path]/route.ts:69` currently does
`new Response(await upstreamResponse.arrayBuffer(), …)`, which buffers the entire upstream
response before replying. Applied to a stream that never ends, it hangs forever.

The fix is narrow: when the upstream `content-type` starts with `text/event-stream`, return
`upstreamResponse.body` directly instead of buffering, with `Cache-Control: no-cache` and
`Connection: keep-alive`. Every other route keeps its current behaviour exactly.

### 8.3 Deployment note

`deploy/api/nginx.conf` needs `proxy_buffering off;` (and `proxy_read_timeout` raised) on the
stream location. Without it, nginx accumulates events and delivers them in clumps, which looks
like the feature is broken in production while working locally.

### 8.4 Client

`apps/web/hooks/useDyslexicStream.ts` opens an `EventSource` against `/api/dyslexic/stream`,
exposes the last event and a connection state, and reconnects with backoff. Each page subscribes
and refetches what the event touched.

**Degradation is explicit.** After three failed reconnects the hook falls back to a 30-second
poll and reports `degraded`, which the UI shows as a small "reconnecting" indicator. Correctness
never depends on the stream — the duplicate guard is in the database. The stream only decides how
soon you find out.

---

## 9. Analytics

All computed on read, one query per panel, grouped by user.

| Metric | Query |
| --- | --- |
| Companies added | `COUNT(dyslexic_companies WHERE added_by = u)` |
| Contacts added | `COUNT(dyslexic_contacts WHERE added_by = u)` |
| Emails sent | `COUNT(dyslexic_outreach WHERE sent_by = u AND kind = 'initial')` |
| Follow-ups sent | `COUNT(dyslexic_outreach WHERE sent_by = u AND kind = 'follow_up')` |
| Replies received | `COUNT(dyslexic_outreach WHERE sent_by = u AND outcome = 'replied')` |
| Meetings scheduled | `COUNT(… outcome = 'meeting_scheduled')` |
| Sponsors closed | `COUNT(… outcome = 'sponsored')` |

The leaderboard runs these as a single grouped query joined to `users`, ordered by a weighted
`score`. Weights live in one module constant so they can be tuned without touching query code:

```python
LEADERBOARD_WEIGHTS = {
    "companies_added": 1,
    "contacts_added": 1,
    "emails_sent": 3,
    "follow_ups_sent": 2,
    "replies_received": 5,
    "meetings_scheduled": 8,
    "sponsors_closed": 20,
}
```

Ranking rewards outcomes over volume, so adding fifty junk companies does not beat closing one
sponsor. `?period=30d` adds a `created_at`/`sent_at` cutoff.

---

## 10. Frontend

One entry in `navItems` (`Sidebar.tsx:35`) — `{ label: "Dyslexic", href: "/dashboard/dyslexic",
icon: Handshake }` — placed after Meetings. Everything lives inside `DashboardShell`, inheriting
the Topbar, mobile drawer and neobrutalist styling. No new shell, no new design language.

Section-level tabs (Dashboard · Companies · Contacts · Leaderboard) render as links styled with
the same active treatment the sidebar uses: `bg-main text-main-foreground border-2 border-border
shadow-light`.

### Pages

**Dashboard** `/dashboard/dyslexic` — a `StatCard` per counter returned by `GET /stats`, reusing
`components/dashboard/StatCard.tsx`, then a "Your follow-ups due" panel with overdue items
marked, a live activity feed, and a top-five leaderboard preview linking to the full page.

**Companies** `/dashboard/dyslexic/companies` — searchable, stage-filterable table matching the
`MembersContent.tsx` pattern (`border-2 border-border`, `bg-[#111]` header row). Stage renders as
a `Badge`. "Add Company" opens a Dialog with two fields, then shows research arriving live.

**Company detail** `/dashboard/dyslexic/companies/[id]` — three regions: the research panel
(with sources, confidence, and Retry on failure), the contacts table with per-contact state
(claimed by X · contacted by Y on date), and the timeline down the right. This is where the
generate → copy → "I've Sent Email" loop happens: the draft opens in a Dialog with an editable
body, a Copy button, and the send button below it.

**Contacts** `/dashboard/dyslexic/contacts` — every contact across companies, filterable by
status, for finding who still needs an email.

**Leaderboard** `/dashboard/dyslexic/leaderboard` — ranked table with an all-time / 30-day
toggle, and the current user's row highlighted.

### Conventions followed

Client components with `useState`/`useEffect`/`fetch` against relative `/api/dyslexic/*` URLs,
thin wrappers in `lib/dyslexic.ts` mirroring `lib/dashboard.ts` and `lib/users.ts`. `@bnb/ui`
components imported from `@bnb/ui`, with the known caveat that `sidebar`, `form` and `resizable`
are not exported. Toasts via the exported `sonner`. Loading states use the existing
`PageSkeleton` / `Skeleton`; empty states use `EmptyState`.

---

## 11. Error handling

| Failure | Behaviour |
| --- | --- |
| Gemini unavailable / key missing | `research_status = "failed"` with the reason. Company still usable. Retry button. Email generation returns 503 with a clear message; the volunteer can still write the email themselves and log the send. |
| Model returns unparseable JSON | Raw text stored in `research_raw`, status `failed`, Retry offered. |
| Duplicate company domain | 409 with the existing company id and name; UI links to it. |
| Contact already contacted | 409 naming the volunteer and date. Partial unique index catches the race. |
| Claim held by someone else | 409 with holder name and expiry; UI offers a read-only view of prior drafts. |
| Stream drops | Reconnect with backoff, then poll every 30s, `degraded` shown in the UI. |
| Redis down | `event_bus` already degrades to local-only. Single-node updates still work; multi-node clients rely on the poll fallback. |
| Background research task crashes | Wrapped; status set to `failed`, error recorded, exception logged. Never leaves `running` on an unhandled failure. |

---

## 12. Testing

Backend, `pytest` + `httpx` against aiosqlite following `tests/conftest.py` and its HMAC signing
helper:

- `test_dyslexic_companies.py` — create, domain normalisation and dedupe 409, list filters,
  archive, stage patch.
- `test_dyslexic_contacts.py` — create, per-company email uniqueness, cross-company duplicate
  warning, claim/release, claim conflict 409, claim expiry.
- `test_dyslexic_outreach.py` — the core guarantees: a second initial send returns 409; the
  partial unique index rejects a concurrent duplicate; a send creates exactly one follow-up;
  outcome recording resolves the follow-up and advances stage; a contact never ends up with two
  pending follow-ups whichever path logs the chase; stage never moves backwards.
- `test_dyslexic_stats.py` — aggregates match hand-built fixtures; 30-day window excludes older
  rows; leaderboard ordering follows the weights.
- `test_dyslexic_research.py` — the Gemini client is mocked. Covers parse success, fenced JSON,
  unparseable output, missing API key, and that a research failure leaves the company usable.

The AI is never called in tests. Every model interaction goes through a small seam in
`research.py` / `emails.py` that tests substitute.

Frontend verification is manual against a running stack, with a documented multi-tab check: two
browser sessions, one claims a contact, the other sees the claim appear and is refused the send.

---

## 13. Configuration

```bash
# .env.example additions
DYSLEXIC_GEMINI_MODEL=gemini-3.6-flash
```

`GEMINI_API_KEY` already exists and is reused. No other new configuration.

---

## 14. Suggested build order

Each step leaves the module working, just with less in it.

1. **Schema** — six models, Alembic revision, run migrations, verify create/rollback.
2. **Companies and contacts** — CRUD routes, schemas, dedupe, tests. No AI, no realtime.
3. **Outreach loop** — claim, send, duplicate guard, follow-ups, outcomes, timeline, audit.
   This is where the product's core promise is either kept or not; it gets the heaviest tests.
4. **Frontend** — sidebar entry, four pages, dialogs, wired to steps 2 and 3. Usable end to end
   at this point, minus AI and live updates.
5. **AI** — research and email generation behind the mockable seam.
6. **Realtime** — SseHub, stream route, proxy change, client hook, nginx note.
7. **Analytics** — stats, leaderboard, activity feed.

Steps 5, 6 and 7 are independent of each other and can be done in any order once 1–4 are in.

---

## 15. Open items for implementation

None blocking. Two things to confirm against reality while building:

- The exact `google-genai` call shape for search grounding on `gemini-3.6-flash`. Google now
  recommends the Interactions API over `models.generate_content`; the seam in `research.py`
  isolates this, so switching costs one function.
- Whether the deployed nginx sits in front of the stream path at all, or whether Next handles it
  directly in the current topology. Check before assuming §8.3 is needed.
