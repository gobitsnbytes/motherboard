# Digital onboarding implementation plan

## Goal

Add a portal-first onboarding workflow for volunteers and fork leads without replacing the existing signature engine. A case owns its participants, document evidence, review history, and the child signature requests that produce canonical sealed PDFs.

## First delivery

1. Add case, participant, document, and review tables with UUIDs, hashed portal tokens, immutable review rows, and links to existing `signature_requests`.
2. Add a template manifest for the six supplied DOCX templates. The manifest defines the semantic fields, audience, and PDF overlay coordinates discovered from the raw OOXML structure.
3. Add a document service that copies the source DOCX, appends a deterministic filled-data section to the evidence DOCX, converts it with headless LibreOffice, and creates a child signature request with the existing field overlay/seal pipeline.
4. Add authenticated staff endpoints for case creation, case listing/detail, review decisions, teammate invitations, and certificate initiation.
5. Add scoped public portal endpoints for participant/parent completion. A token can only read and mutate its own party and its assigned documents.
6. Add a dashboard page and public portal page. Keep the UI small and reuse the signature portal for signatures.
7. Install LibreOffice Writer in the API image and copy the repository templates into the image. If the renderer is unavailable, document generation fails closed rather than silently producing a degraded canonical PDF.

## Explicit non-goals

- No new generic workflow engine.
- No PDF AcroForm generation in the first delivery; fields remain web-interactive and the sealed PDF is static.
- No replacement of the existing fork checklist or signature engine.
- No automatic approval, self-approval, or certificate initiation before required documents are accepted.

## Verification

- Unit tests for age gating, token hashing/scope, self-approval prevention, and template manifest coverage.
- API tests for volunteer and fork happy paths plus minor consent and teammate isolation.
- Typecheck/build the web app.
- Render at least one filled template in the container with LibreOffice and inspect the resulting PDF pages before release.
