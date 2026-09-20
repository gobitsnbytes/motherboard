# Discord-backed members page

## Goal

Make the Motherboard Members page represent real people who have signed in with Discord. Generic database users, service accounts, manually created users, and historical placeholders must not appear.

## Source of truth

A visible member must have an active `users` row joined one-to-one to a `discord_accounts` row created through Discord sign-in. The Discord account supplies the stable identity, username, avatar, and sync state. The linked Motherboard profile supplies the editable display name, contact email, title, and bio. Active Discord-synced IAM memberships supply access roles.

The page does not enumerate every Discord guild member. A person appears after their first Motherboard Discord sign-in.

## API

Add a dedicated read-only members endpoint instead of changing generic `/api/users`, which is also used by finance and administrative selectors.

Each member response contains:

- Motherboard user ID and active status;
- profile display name, email, title, and avatar;
- Discord ID and username;
- last Discord sync timestamp;
- active IAM groups derived from Discord role sync;
- account creation timestamp.

The query uses joins/eager loading rather than per-member role queries. It excludes users without a Discord account and inactive users. Authorization continues to require `iam.users.read`.

## Interface

The existing page structure stays intact. Replace the misleading columns with Member, Discord, Profile email, Roles, and Joined. Render the profile or Discord avatar when available, show `@username`, and render synced IAM groups as badges. Search matches display name, Discord username, email, and role names.

Empty and error states explicitly describe signed-in Discord members. No new component library or state-management dependency is added.

## Verification

Backend coverage proves unlinked and inactive users are excluded, linked users are returned once, and Discord-synced roles are included. Frontend verification covers the response type, filtering fields, empty state, and accessible table labels. CI lint and backend tests must pass before deployment.

## Non-goals

- Importing the full Discord guild roster.
- Restoring Notion identity sync.
- Deleting generic users needed by historical records.
- Changing finance or administrative user selectors.
