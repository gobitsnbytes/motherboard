# Discord is the source of truth for access

One direction only: **Discord roles -> Motherboard memberships**. Motherboard never writes roles back.

```
Discord role change ──> bot event ──> POST /api/sync/member (X-Internal-Secret) ──┐
Member signs in    ──> /api/auth/upsert reads their roles with their own token ───┼─> sync_member_roles()
Hourly safety net  ──> run_sync() full guild sweep ───────────────────────────────┘   (one rule: diff_groups)
```

- `diff_groups` in `apps/api/app/provisioning/sync.py` is the only rule. It adds a membership only when the person is not already in the group by any source, and removes only `discord_sync` memberships. Manual memberships are never touched.
- `role -> group` comes from `discord_role_mappings` (IAM page). A role with no mapping grants nothing.
- Leaving the server (`roles: null`) removes sync-owned memberships.
- A Discord outage never blocks sign-in and never wipes access: lookups that fail leave memberships as they are.
- A person who has never signed in has no account yet. Their first sign-in resolves their roles immediately.
- What a group may do is separate: grants on the group. `python -m app.iam.role_policy` prints the reviewed leadership baseline as a diff; `--apply` writes only the missing grants and one audit row. Nothing runs it on startup.

## Operating it

- VPS `.env`: `ENABLE_SYNC_SCHEDULER=true`, `SYNC_INTERVAL_MINUTES=60`. The old example shipped `false`, so check the live value.
- Bot env needs `API_INTERNAL_SECRET` and `MOTHERBOARD_API_URL`. The bot needs the Server Members intent (already requested in `apps/bot/index.js`).
- Freshness: IAM > Sync history shows each sweep. A live push that fails is retried once, then the sweep repairs it.
