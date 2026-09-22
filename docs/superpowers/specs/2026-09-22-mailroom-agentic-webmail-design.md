# Mailroom agentic webmail design

## Product

Mailroom is a small webmail plugin inside Motherboard for `@gobitsnbytes.org` accounts. It reads and changes mail directly through Dovecot IMAP and sends through the existing mail stack. Motherboard does not copy message bodies into PostgreSQL.

The first release covers sign in, inbox and folders, safe message rendering, attachments, search, compose, reply, archive, delete, read state, and a few focused SparkCloud actions. The interface should feel closer to a quiet reading app than an admin dashboard.

## Decisions

- Dovecot remains the source of truth for messages, folders, flags, drafts, and sent mail.
- A user may sign in with their mailbox password or a short lived OTP delivered to the mailbox.
- Password sign in is always available, including on a new device where the user cannot yet read an OTP.
- Motherboard stores the mailbox credential because it needs to open later IMAP and SMTP sessions. It stores ciphertext only through the repository's encrypted column type. The encryption key stays in server configuration.
- The browser receives an opaque, HttpOnly session cookie. It never receives the stored mailbox password.
- SparkCloud may process mail for user requested writing tools and lightweight automatic triage. The product shows when AI has changed a draft and never sends a generated message without a user action.
- Full body search uses IMAP search. A small in-memory cache may hold the current page of headers during a request, but no durable mail mirror is allowed.

## Shape

Mailroom should be a new plugin rather than an expansion of the existing `email_server` plugin. `email_server` is an administrator tool with server controls and logs; Mailroom is an end user mailbox. The two plugins share the deployed mail host and configuration names, but they have separate permissions and screens.

The plugin has four small backend units:

1. `auth` validates credentials against IMAPS, issues OTPs, encrypts stored credentials, and manages sessions.
2. `mailbox` wraps IMAP operations and converts MIME messages into a stable API shape.
3. `sender` submits mail through the existing authenticated submission path and appends sent/draft copies through IMAP.
4. `assistant` sends a bounded message context to SparkCloud for summarize, reply, rewrite, and triage actions.

Keep these units behind narrow interfaces so the deployed mail protocol or model endpoint can change without rewriting the UI.

## Data kept by Motherboard

`mailroom_accounts` contains the normalized mailbox address, encrypted mailbox password, preferences, and timestamps. `mailroom_sessions` contains a hashed opaque token, account id, expiry, last use, and revocation time. `mailroom_otp_challenges` contains a hashed code, expiry, attempts, and consumed time. AI preferences may include tone, signature behavior, and whether automatic triage is enabled.

No table stores subjects, senders, recipients, snippets, bodies, attachments, or model transcripts.

## Authentication flow

Password login validates the address domain, attempts an IMAPS login over TLS, stores the encrypted credential after success, rotates the session token, and sets the session cookie. Errors use one generic message so the endpoint does not reveal which mailboxes exist.

OTP login accepts only an account that has already completed password login and has a usable stored credential. The server creates a six digit code with a short expiry, stores its keyed digest, limits resend and verification attempts, then sends the code through the existing outbound path. Successful verification consumes the challenge and rotates the session.

Sessions expire after inactivity and can be revoked from the account screen. Sign out removes the cookie and revokes the server record.

## Mail API

The first API surface is deliberately small:

- session status, password login, OTP request, OTP verification, and logout
- list folders and paginated message summaries
- fetch one message and its thread neighbours
- stream one attachment after access checks
- search through IMAP
- update flags, move, archive, and delete
- save draft and send message
- run one assistant action against a message or draft

IMAP work is blocking, so FastAPI runs it in a bounded worker thread with connection and command timeouts. Each request opens a short lived connection using the decrypted credential. Same VPS placement keeps this cheap and avoids a connection pool that would hold many credentials in memory.

## Message rendering

The server parses MIME and returns separate plain text, sanitized HTML, inline image, link, and attachment data. HTML is sanitized with an allowlist. Scripts, forms, remote embeds, event handlers, dangerous URLs, and CSS that can escape the message surface are removed. Remote images start blocked and can be loaded per message. Links show their real destination and open with safe browser isolation.

Inline images referenced by `cid:` are served through authenticated attachment routes. The raw message is available as a download for debugging, not rendered directly.

## Interface

Desktop uses three regions: a slim folder rail, a message list, and the reading pane. Mobile shows one region at a time with normal back navigation. Compose opens as a focused sheet on wide screens and a full page on mobile.

Visual rules:

- neutral surfaces, one warm accent from the existing bits&bytes system, and semantic tokens from `@bnb/ui`
- compact rows with a comfortable 44 pixel interaction target
- sender and subject carry the hierarchy; metadata stays quiet
- no ornamental cards, gradients, glass effects, or dashboard metrics
- visible focus states, complete keyboard navigation, and restrained 150 to 200 ms state transitions
- a plain text fallback is always one click away when HTML looks suspicious

The working name is **Mailroom**. It is clear inside an internal system and does not sound like a generic AI product.

## Agent behavior

The assistant lives beside the composer and message toolbar. Version one supports:

- summarize the open thread
- draft a reply from a short instruction
- rewrite a selected draft for clarity, brevity, warmth, or formality
- suggest archive, reply, or keep for lightweight triage

The model receives only the current thread content required for the action, the user's instruction, and their saved writing preferences. Tools return structured output. Mail mutations stay in normal application code; the model cannot send, delete, move, or fetch arbitrary mail.

## Failure handling

An expired mail password returns the user to Mailroom sign in without destroying the Motherboard session. IMAP and SMTP failures show a retryable state and retain local draft text in the browser. AI failure leaves the draft unchanged. A send request uses an idempotency key so a retry cannot create two outbound messages.

## Verification

Backend tests cover credential validation, session rotation, OTP expiry and attempt limits, mailbox isolation, MIME sanitization, IMAP pagination, and send idempotency. Protocol clients use fakes in unit tests and a local test mailbox for integration tests.

UI verification covers keyboard use, narrow screens, unread and empty states, blocked remote images, attachment download, draft recovery, and all assistant actions. The release gate includes a manual login against one test mailbox on the VPS, one inbound message, one reply, and confirmation that the Motherboard database contains no mail content.

## Delivery slices

1. Plugin shell, encrypted account/session tables, password login, and session status.
2. Inbox, folders, message reading, sanitized HTML, images, links, and attachments.
3. Compose, reply, drafts, send, flags, move, archive, delete, and search.
4. OTP login, SparkCloud actions, lightweight triage, and final privacy checks.

