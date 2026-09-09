# Shared Operational Shell UI/UX Redesign

## Goal

Replace the current page-by-page visual treatment with one coherent bits&bytes™ operational interface while preserving existing routes, data flows, and user actions. The redesign should make the app easier to scan, easier to operate, and visibly aligned with the official brand guide.

## Scope

In scope:

- Shared dashboard shell, sidebar, top bar, page header, navigation groups, and responsive mobile navigation.
- Shared visual primitives used by dashboard, meetings, finance, signatures, contracts, and Dyslexic CRM surfaces.
- Navigation labels and grouping, with route URLs preserved.
- Search/filter/toolbars, status treatments, empty/loading/error states, tables, cards, and detail-page composition.
- Typography, spacing, color, border, focus, shadow, and responsive behavior.

Out of scope:

- API contracts, database schemas, authentication rules, or domain workflows.
- Replacing route URLs or removing existing capabilities.
- Adding a new UI dependency when existing React, Tailwind, Lucide, and shared UI primitives cover the need.
- Decorative animation or visual effects that do not improve comprehension.

## Design principles

1. **One operational grammar.** Every authenticated page follows: app chrome → page title/context/action row → optional summary strip → dominant work surface → supporting details.
2. **Hierarchy before decoration.** Use one clear primary action, compact secondary actions, and fewer competing panels. A surface earns its border and shadow by organizing work.
3. **Brand with restraint.** Use burgundy `#97192c` for primary actions and focus, orange `#fc920d` for emphasis, and approved neutrals for chrome and document surfaces. Use the official bits&bytes™ name and logo rules.
4. **Dense, not cramped.** Reduce repeated labels and oversized whitespace while preserving readable line height, target sizes, contrast, and keyboard focus.
5. **Stable behavior.** Presentation changes must not alter API calls, route semantics, permission checks, or existing domain actions.
6. **Responsive by composition.** Tables become readable stacked rows or horizontal scroll regions; side navigation becomes a compact drawer; primary actions remain reachable.

## Information architecture

Keep all current URLs. Consolidate the visible navigation into these groups:

- **Overview:** Dashboard, activity, profile, settings.
- **Work:** Meetings, forms, signatures, contracts, Dyslexic CRM.
- **Governance:** IAM, members, audit, forks, plugins.
- **Finance:** Finance overview, requests, accounts, cards, reports.
- **Network:** Fork and community-related destinations.

The active route must be obvious through a burgundy treatment and a text label; icons alone are insufficient. Admin-only destinations remain permission-gated and visually secondary to daily work.

## Shared component system

Prefer existing shared components and tokens. Add only the smallest missing primitives:

- `AppShell`: responsive chrome and content frame.
- `PageHeader`: eyebrow/breadcrumb, title, description, and action slot.
- `WorkSurface`: dominant table/list/editor container with consistent overflow and empty states.
- `Toolbar`: search, filters, tabs, and result count with mobile wrapping.
- `StatusBadge`: consistent semantic status colors and accessible text.
- `StatCard`: reserved for meaningful summary values, never as a decorative grid.

Existing components should be restyled or composed before new abstractions are introduced. Avoid one-off page-specific copies.

## Page treatment priorities

1. Dashboard shell and navigation, because every authenticated route inherits it.
2. Meetings, because the current repeated card grid is the clearest problem shown in the reference screenshot.
3. Finance and signatures, because their workflows depend on scanability, status, and trust.
4. Contract assistant and Dyslexic CRM, using the same header/toolbar/work-surface grammar.
5. Public and utility states (login, verify, signing, not-found, empty/loading/error) for brand consistency.

## Interaction and accessibility

- Use visible `focus-visible` rings with burgundy contrast.
- Keep interactive targets at least 44px on touch layouts.
- Preserve semantic headings, labels, table relationships, and status text.
- Use motion only for state feedback; honor reduced-motion preferences.
- Ensure text and controls meet WCAG AA contrast.
- Preserve copy/link affordances and expose truncated values through title or detail affordances.

## Technical approach

- Reuse the existing Tailwind tokens and `packages/ui` components.
- Centralize visual changes in shared shell/styles where possible.
- Keep client components client-only where interaction requires it; leave static page composition server-rendered.
- Avoid new dependencies and avoid component memoization unless profiling or an expensive list justifies it.
- Use CSS for layout and interaction states before adding JavaScript state.

## Verification

- `bun run typecheck`
- `bun run build`
- Existing relevant tests.
- Manual smoke pass for dashboard, meetings, finance, signatures, contract assistant, Dyslexic CRM, login, and public signing/verification.
- Check desktop and narrow mobile widths, keyboard navigation, reduced motion, focus visibility, and contrast.

## Acceptance criteria

- The authenticated app reads as one product rather than unrelated screens.
- Meetings no longer present a repetitive card wall as the primary work surface.
- Navigation is grouped and understandable without changing route URLs.
- Primary action, current location, status, and next step are obvious on each priority screen.
- Existing workflows and permissions continue to function.
- Build and typecheck pass with no new warnings attributable to the redesign.
