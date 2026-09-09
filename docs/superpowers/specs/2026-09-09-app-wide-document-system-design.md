# Motherboard document-system redesign

## Goal

Bring the whole Motherboard experience into the visual language established by
the approved form builder: a quiet document workspace for primary work, held
inside direct, dark operational chrome. This is a UI-only redesign. Existing
routes, permissions, APIs, data, and workflow semantics remain unchanged.

## Product direction

The product is used by Foundation operators doing consequential work in a
desktop workspace, often for extended sessions. The default is therefore a
restrained product UI: dark navigation and controls, a warm-neutral work
canvas, and burgundy/orange only for action, selection, or meaningful state.

References are the approved form builder, Notion's calm writing surface, and
Linear/Stripe's operational density. This is not a generic SaaS dashboard:
the bits&bytes™ brand retains its 2px borders, hard press feedback, and
high-contrast directness without turning every data row into a card.

## Rollout order in one release branch

### 1. Shared internal shell

- Make the dashboard and finance chrome one system: brand mark, route context,
  responsive navigation, compact operator controls, and predictable back
  navigation.
- Standardize action, secondary, destructive, status, input, table, empty,
  loading, and error states. Every interactive control keeps a visible focus
  state and a 44px touch target.
- Keep work content on a document canvas rather than isolated dark cards.
  Dense data surfaces use rows, rules, and sections; focused editors use a
  narrow reading column plus a contextual inspector when useful.

### 2. Internal operational routes

Redesign overview, profile, members, forks, meetings, forms, signatures,
contract assistant, IAM, audit, settings, Dyslexic, plugins, and finance.

- Overview and lists lead with the next real action and source-backed status.
- Records, legal documents, configuration, and forms use document hierarchy:
  title, context, content, then actions.
- Tables and audit streams remain dense, scrollable, and responsive; they do
  not become card grids.
- Finance removes its separate visual language and duplicate navigation while
  retaining finance-specific information hierarchy.
- Existing empty, loading, unavailable, permission, and failure states are
  rewritten into the shared vocabulary instead of being hidden or faked.

### 3. Public routes

Apply the same tokens and typography to login, verification, signing, and
public forms after the internal experience is coherent. Public routes have a
lighter, distraction-free canvas and only task-essential navigation; they do
not inherit internal dashboard controls.

## Interaction and accessibility contract

- The navigation collapses structurally on small screens; no route relies on
  hover, a desktop-only side panel, or horizontal overflow.
- Keyboard focus is visible, icon-only controls have labels, forms keep
  persistent labels and nearby error text, and status uses wording/icons in
  addition to colour.
- Motion is limited to 150–250ms feedback and state changes, is never required
  to reveal content, and respects reduced-motion preferences.
- Destructive actions remain explicit. No visual change may alter authorization
  or make optimistic claims about a backend state.

## Out of scope

- New modules, backend routes, migrations, permissions, and data models.
- Replacing working domain flows merely to make screens look similar.
- Decorative animation, glass effects, gradient text, side-accent cards,
  fabricated metrics, or a wholesale component-library rewrite.

## Verification

- Exercise every route at desktop and mobile widths, including empty/loading/
  error states where available.
- Run web typechecking and production build checks.
- Review navigation, keyboard focus, contrast, overflow, unsafe rendering, and
  regressions in authenticated and public flows before the single prod push.
