# Legal Agent Qenlo Implementation Plan

## 1. Retrieval foundation

- Add the Qenlo Python dependency and private retrieval configuration.
- Add an embedding-provider seam with explicit availability/error states; do not place credentials in code.
- Create a Qenlo-backed retrieval service with durable collections, a source manifest, stable record IDs, and keyword fallback.
- Test chunking, manifest changes, filtering, and fallback before routing requests through it.

## 2. Legal `/ask` and index lifecycle

- Route existing OKF and completed-contract source chunks through the retrieval service.
- Keep the current response contract and source labels.
- Add a protected status/rebuild surface that redacts secrets and exposes health only.
- Test authorization, fallback, stale-index handling, and no cross-contract retrieval.

## 3. Inbox behaviour and operations

- Extend the legal inbox handler to answer policy questions from verified internal mail and continue attachment analysis for contracts.
- Record redacted IMAP/SMTP failures and expose status in the legal dashboard API.
- Keep unauthenticated/external email limited to attachment intake; do not trust a visible `From:` header.
- Test plain-email replies, duplicate handling, bad attachments, and transport retry conditions.

## 4. Deployment verification

- Add the Qenlo index directory to the API service's persistent deployment configuration.
- Configure IMAP credentials in deployment secrets, never source control.
- Verify a real external-mailbox round trip plus service restart/index persistence before enabling the inbox scheduler.
