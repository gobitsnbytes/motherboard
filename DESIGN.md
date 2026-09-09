# Motherboard interface system

## Register

Product UI.

## Physical scene

An operator moves between finance, governance, meetings, and evidence workflows on a laptop in a bright office, scanning quickly but making consequential decisions that must remain legible and auditable.

## Direction

Motherboard is a warm operational instrument, not a generic SaaS dashboard. The shell uses a burgundy control rail and a paper-like work canvas. Orange marks the next action or active state. Content surfaces are quiet, rectangular, and evidence-first.

## Tokens

- Ink: `#120f0a`
- Burgundy: `#97192c`
- Burgundy deep: `#5b0f1a`
- Orange: `#fc920d`
- Canvas: `#f4f1ec`
- Paper: `#ffffff`
- Rule: `#120f0a`
- Muted ink: `#625b52`

## Type

- Headings: Inter, high contrast through size and weight.
- Long-form body: Merriweather for reading-heavy public and legal surfaces.
- Metadata and IDs: JetBrains Mono.
- Avoid all-caps except compact navigation labels and machine metadata.

## Layout and interaction

- The desktop shell is a fixed burgundy rail plus a warm scrollable canvas.
- Prefer sections, tables, and inline disclosure over nested cards and modal-first flows.
- Minimum interactive target is 44px. Every async mutation has visible pending, success, and failure feedback.
- Status is never communicated by colour alone.
- Focus rings use orange on dark chrome and burgundy on the light canvas.
- Respect reduced motion. No decorative motion that competes with evidence.
