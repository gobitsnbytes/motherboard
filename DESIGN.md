# Motherboard Design System

## Visual Direction

An operational product UI with a structured editorial backbone: warm neutral surfaces, deep burgundy navigation and emphasis, controlled orange for active attention, crisp borders, restrained shadows, and occasional print-like texture on context surfaces only.

## Color Roles

- Burgundy core: `#97192c`
- Burgundy deep: `#5b0f1a`
- Ink neutral: `#120f0a`
- Muted neutral: `#716f6c`
- Light neutral: `#f7f7f5`
- Orange attention: `#fc920d`
- Warm gradient accent: `#c94218`
- Success: a high-contrast green reserved for positive state
- Danger: a high-contrast red reserved for destructive state

Use the existing CSS variables as the implementation source of truth. Burgundy is for structure and primary actions; orange is for attention, selection, and active change. Do not use gradients for text or as a default card treatment.

## Typography

Use the existing heading/body font stack in the app. Product labels and controls use a legible sans with a compact fixed scale. Headings use strong weight and balanced wrapping; body copy stays short and readable. Decorative script type is reserved for rare brand surfaces, never for controls or data.

## Layout

- Desktop: persistent navigation plus a focused content column.
- Tablet: collapse secondary navigation while preserving location and scope context.
- Mobile: stack content, convert wide tables into labelled rows, and keep primary actions reachable.
- Use full borders and small hard shadows where the neobrutalist system already does so; avoid oversized radii and nested cards.

## Interaction

Every action exposes default, hover, focus, active, disabled, loading, success, error, and forbidden states. Motion is short and state-driven, with a reduced-motion fallback. Destructive changes require explicit confirmation and show the resulting audit context.

## IAM Surface

The IAM console is organized around Overview, People & Groups, Access Review, Grants, Discord Mappings, and Audit. The most important visual object is the effective-access explanation: permission, scope, source, expiry, and the path that granted it.
