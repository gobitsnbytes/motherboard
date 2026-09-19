# Legal Agent Qenlo Retrieval and Email Operations

## Goal

Make `legal@gobitsnbytes.org` a working email-native legal agent. It must answer ordinary legal-policy questions using approved Foundation context, ingest attached contracts for review, and retrieve relevant material through a lightweight local Qenlo index.

## Scope

- Use `llms-full.txt` as the versioned Qenlo documentation source used to implement and validate the adapter. It is not queried at request time and is not legal-agent knowledge.
- Use Qenlo as an embedded retrieval index only. PostgreSQL remains canonical for contracts, findings, users, permissions, and audit data.
- Index existing OKF markdown into a durable `okf` Qenlo collection and completed-contract clauses into a distinct `executed_contracts` collection.
- Preserve the existing deterministic token-overlap retrieval as an automatic degraded-mode fallback.
- Process two inbound-email modes: policy questions without files and contract-review emails with PDF/DOCX attachments.
- Surface safe operational status for inbox readiness, last successful poll, last poll error, active retrieval backend, and index revision/counts.

## Non-goals

- Qenlo is not the authoritative legal datastore, a multi-process service, or an authorization system.
- The agent does not give definitive legal advice, accept instructions that change a contract, sign documents, or disclose one contract to an unauthorized sender.
- The agent does not execute actions solely from email content.

## Architecture

```
OKF markdown + completed contract clauses
                 |
       chunk, hash, embed
                 |
     Qenlo durable collections
        |                 |
      okf             executed_contracts
        \                 /
         semantic top-k retrieval
                 |
      source-labeled context builder
                 |
       legal answer / contract review
                 |
     dashboard `/ask` or IMAP email reply
```

`LegalRetrievalService` owns indexing and searches. It receives plain source chunks and returns source-labelled hits; it knows neither FastAPI request state nor email transports. A configured embedding provider supplies fixed-dimension vectors. The provider/model name, vector dimension, source hash, and index schema version form the index manifest. A mismatch rebuilds the affected collection atomically before it can serve results.

The runtime stores Qenlo files in a configured persistent, private directory mounted into the API container. The collection directory is never served by HTTP or committed to Git.

## Data and access boundary

The dashboard agent is available to every authenticated user whose verified account email ends in `@gobitsnbytes.org`; no further role grant is required for the OKF-policy-answer mode. The API derives this from the resolved authenticated principal, never from a caller-supplied email address. Non-members receive `403`.

The OKF collection contains only approved project policy markdown. Each record stores a stable chunk ID, source path, title, source hash, category, and chunk ordinal.

The executed-contract collection contains only clauses whose contract/envelope is completed. It stores a stable clause-derived record ID, canonical contract UUID, clause UUID/ref, title, lifecycle status, and source hash. Dashboard retrieval applies the authenticated user's existing contract-access scope before retrieved content is placed into an LLM prompt. Email retrieval never exposes completed-contract material to arbitrary external senders; external email answers use OKF only unless the sender has an explicit trusted internal identity and authorization path.

## Email behaviour

The IMAP worker handles unseen messages idempotently by Message-ID.

- A message from a verified `@gobitsnbytes.org` mailbox without a supported attachment is treated as a policy question. The agent retrieves approved OKF context, drafts a bounded answer with source labels and a human-review disclaimer, and replies in-thread.
- A message with supported PDF/DOCX attachments is ingested through the current analysis pipeline. The reply contains only that submission's high-level review, explicit findings, and next steps.
- A sender's displayed `From:` address is not sufficient proof of organization membership. The inbound mail system must provide validated sender/authentication results (for example, DMARC-aligned SPF/DKIM) or a trusted internal delivery identity before the agent treats a message as an internal policy request. Unverified external senders receive only the attachment-review intake response and never completed-contract retrieval.
- Unsupported, oversized, empty, malformed, or unauthorised submissions receive a concise safe response; stack traces, credentials, and internal configuration are never emailed.
- A send failure or retrieval failure leaves the message unread for bounded retry and records a redacted operational error. A successfully handled message is marked seen only after its durable ingest/event transaction completes.

IMAP delivery requires deployment-time values for `LEGAL_INBOX_IMAP_HOST`, `LEGAL_INBOX_IMAP_USER`, and `LEGAL_INBOX_IMAP_PASSWORD`. SMTP requires valid deployment-time transport credentials. The code must report missing configuration clearly but never return or log credential values.

## API and operational contract

`POST /api/contract-assistant/ask` retains its response shape and gains semantic source chips when Qenlo is ready. A protected agent-status endpoint reports booleans/counters only: IMAP configured, scheduler active, last success, last error category/time, Qenlo readiness, backend in use, collection revisions, and indexed item counts. It never reports mailbox usernames, hostnames, credentials, raw messages, or document content.

Rebuilding an index is a staff-authorized operation. It is rate-limited, serialised by a process lock, builds into a temporary collection, validates dimensions and source manifest, then atomically promotes it. Query traffic uses the prior ready revision until promotion succeeds.

## Configuration

- `LEGAL_RETRIEVAL_BACKEND=qenlo|keyword` (default `keyword` until provisioned)
- `LEGAL_QENLO_DATA_DIR` (private persistent directory)
- `LEGAL_EMBEDDING_PROVIDER` and `LEGAL_EMBEDDING_MODEL`
- `LEGAL_EMBEDDING_DIMENSION` (validated against the provider response)
- `LEGAL_INBOX_MAX_ATTACHMENT_BYTES` and a supported-extension allowlist
- Existing IMAP/SMTP settings, supplied only in deployment secrets

No credential defaults are added. Production configuration changes are separate from source deployment.

## Failure handling

- If Qenlo, its collection, or embedding is unavailable, `/ask` transparently falls back to the current deterministic retrieval and status reports `keyword_fallback`.
- If a contract index is stale, the response excludes it rather than returning mismatched vectors or a different contract's text.
- If the inbox is not configured, the scheduler status is `not_configured` and the health response names only the missing setting keys.
- Transient IMAP/SMTP failures receive exponential bounded retries; permanent authentication/configuration failures are visible to operators and do not loop-send replies.

## Verification

- Unit tests cover stable chunking, manifest invalidation, Qenlo filtering, fallback retrieval, and no cross-contract result leakage.
- Router tests cover authorized semantic `/ask`, fallback behavior, status redaction, and rebuild authorization.
- Email tests cover ordinary policy-question replies, attached-contract ingestion, idempotency, unsupported attachments, SMTP failure retry, and missing-IMAP status.
- Container validation confirms the Qenlo wheel runs in the Linux API image and that the mounted index survives restart.
- Pre-deployment checks require configured IMAP/SMTP secrets and a real mailbox round trip from an external address before enabling the worker.
