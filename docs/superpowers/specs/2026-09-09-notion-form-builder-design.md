# Notion-like Form Builder

## Goal

Replace the current stacked configuration-card editor with a document-first form authoring experience. Staff should compose a form as naturally as a Notion page; recipients should receive the already-defined branded public form at `/form/{slug}`.

## Product decision

Use a single document canvas with inline blocks and a slash-command insertion menu. Do not add drag-and-drop, a block library sidebar, pages, templates, collaboration cursors, or a custom rich-text engine in this iteration.

The existing `PublicForm.blocks` JSON contract remains the storage format. This redesign changes authoring ergonomics, not public URLs, submitted answers, file retention, idempotency, or the published-form API.

## Staff authoring surface

### Layout

- **Header:** back to Forms, saved state, Responses, Preview, and a single Publish / Unpublish action.
- **Document canvas:** a readable light canvas centered in the dashboard. Title and description are directly editable. The description remains plain Markdown source for this iteration; it is not a WYSIWYG editor.
- **Selected-block inspector:** a right-side panel on desktop. It becomes a bottom sheet on smaller screens. It only shows when a question block is selected.

### Block interactions

- A block is content by default; it has no permanent type badge, heavy border, or visible configuration UI.
- Hovering a block exposes an accessible handle, delete control, and an insertion point below it.
- A keyboard-accessible `+` control at the document end and between blocks opens the same menu as `/` typed into an empty text block.
- The menu contains: Heading, Paragraph, Short answer, Long answer, Email, Multiple choice, Dropdown, File upload, Divider, and Consent.
- New questions receive a contextual, immediately selected prompt placeholder (for example, “What would you like to ask?”), not “Untitled question.”
- Multiple-choice and dropdown options render inline. Enter adds an option; an adjacent remove action deletes one. A choice block cannot be saved with zero options.

### Inspector

The inspector exposes only properties relevant to the selected block:

- Question: required, helper text, answer type, delete.
- Choice / dropdown: required, helper text, option editing, delete.
- File upload: required and the immutable upload policy: five files total, 2 MB per file, PDF/JPG/PNG/DOCX only, 30-day retention.
- Consent: required flag is permanently enabled and the agreement label can be edited.

## Save and publish behavior

- Editing is locally buffered and autosaves after a short idle period; Save remains available as an explicit recovery action.
- Failed saves are visible, actionable, and do not falsely show a saved state.
- Publishing validates every block before changing public availability: required prompts must have labels; select/choice blocks need at least one non-empty option; only supported block types are allowed; form title and unique slug are required.
- Preview opens the existing public form in a new tab. Published forms retain their stable existing `/form/{slug}` link.
- Responses stay in a separate staff view from authoring. The authoring header shows the response count but does not dump JSON into the builder.

## Public form

- Keep the current public form’s white, accessible bits&bytes™ surface.
- Render headings, paragraphs, dividers, question types, consent, and uploads in document order.
- Use native inputs and browser keyboard semantics. Inputs remain at least 44px high with errors next to their fields.
- Markdown descriptions remain escaped text until a dedicated safe Markdown renderer is introduced; no untrusted HTML is rendered.

## Accessibility and responsive behavior

- All controls receive visible focus, semantic labels, and keyboard equivalents.
- On mobile, the canvas fills the viewport; the inspector moves to a dismissible bottom sheet and never obstructs the active field.
- Do not rely on hover, drag, or animation to expose a required action.
- Transitions are limited to transform/opacity, 150–200 ms, and honor reduced-motion preferences.

## Validation and tests

- Unit-test the block normalization/validation helper: invalid labels, no choice options, invalid upload block settings, and valid documents.
- Type-check the web workspace.
- Verify the existing public submission path still accepts a published legacy form without a rewrite.
- Manually verify desktop and narrow-phone editing, slash insertion, selection/inspector behavior, preview, failed save, and publishing validation.

## Delivery boundary

This work is a frontend/editor redesign. The existing backend schema and submission API remain compatible. It does not add real-time collaboration, conditional logic, payments, custom themes, or rich-text editing.
