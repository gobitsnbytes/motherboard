---
type: Policy Rule
title: 🤖 Discord Bot Guide 36b49ed2fc3381378b0bd4649237665f
description: Official bits&bytes legal document from notion-wiki
tags: ['legal', 'governance', 'notion-wiki']
timestamp: 2026-08-04T00:00:00Z
---

# 🤖 Discord Bot Guide 36b49ed2fc3381378b0bd4649237665f

# 🤖 Discord Bot Guide

Owner: Bits Bytes
Tags: Onboarding

<aside>
💡 This guide outlines the features, commands, and workflows of the bits&bytes™ Discord Bot. The bot bridges active communications inside Discord with our Notion databases and SQLite tables to automate chapter operations, event tracking, meeting transcription, and gamification.

</aside>

# 👥 User Perspectives & Workflows

The bot features two distinct operational workflows depending on whether you are a **Fork Lead** managing a local chapter or an **Upstream Team** member overseeing the network.

## 1. Fork Leads' POV (Local Chapters)

<aside>
🎯 As a Fork Lead, your interactions with the bot keep the network synchronized. You are responsible for keeping your team active, reporting events, maintaining your pulse, and utilizing the meeting scheduler.

</aside>

- `/pulse`: Submit regular weekly pulses to log chapter activity. Keeps your chapter status `Active` and registers local updates in Notion.
- `/team-update`: Add or remove members from your local SQLite database chapter, and assign core roles (`Tech Lead`, `Creative Lead`, `Ops Lead`).
- `/team-view`: View your current team structure and roles directly inside Discord.
- `/event-create`: Propose and register new events, setting date, type, description, and expected headcount. Events are automatically synced to Google Calendar via Cal.com.
- `/event-update`: Update event details, log final attendance figures, or adjust event lifecycle states. Setting status to Cancelled automatically cancels the corresponding Cal.com booking.
- `/event-status`: View your upcoming chapter-specific events pipeline.
- `/event-calendar`: Browse the entire network's upcoming events and activities, including upcoming Cal.com scheduled meetings.
- `/report-submit`: Submit bi-weekly or monthly accountability files (with attachments/links) to core staff.
- `/report-status`: View outstanding or submitted reports and verify deadlines.
- `/meet-email`: Register your email address to receive meeting invites and `.ics` calendar attachments.
- `/meet-schedule`: Coordinate syncs, provision temporary voice channels, select durations (15/30/45m), add custom meeting notes, and sync using duration-based Cal.com routing.
- `/meet-transcript`: Retrieve AI-synthesized summaries, transcripts, and action items of past voice channel syncs.
- `/fork-status`: View a complete live dashboard showing your chapter's health metrics and completeness.
- `/fork-health`: Check the health score leaderboard comparing all active chapters.
- `/fork-badges`: View badges and accomplishments achieved by your chapter.
- `/leaderboard`: Check the leaderboard to see how your chapter compares in gamification points.

## 2. Upstream Team's POV (Core Staff & Admins)

<aside>
🛡️ As a Staff Member or Core Admin, the bot acts as your control panel to monitor chapter health, review new fork applications, and run system health checks.

</aside>

- `/admin-add-lead`: Onboard a fork lead directly, bypassing the traditional request pipeline.
- `/merge`: Officially merge a pending fork lead and approve their chapter.
- `/onboarding-complete`: Mark a specific onboarding checklist step complete.
- `/onboarding-status`: Check onboarding checkpoints for pending/active chapters.
- `/archive`: Lock and archive inactive or non-responsive chapters with a specified reason.
- `/forks`: View technical topology and connections of all nodes.
- `/forks-info`: Post or update a single embed listing all active and pending forks info.
- `/report-status`: View outstanding reports status for all nodes.
- `/meet-transcript delete`: Purge an outdated or sensitive meeting transcript.
- `/ping` & `/system-test`: Perform latency tests and test SMTP email dispatch.

# ⚡ Core Feature Deep Dives

## 📅 Meeting Scheduler & AI Transcriber ("Meet" Family)

The meeting system is a powerful integration combining Discord Voice Channels, email invitations (`.ics` calendar attachments), Cal.com sync, and AI recording:

1. **Email Configuration**: Users must run `/meet-email set email:<address>` to register. Without this, you will not receive invitations or calendar files.
2. **Scheduling**: Run `/meet-schedule` to book a sync. You can schedule future meetings (IST timezone) or start one instantly (`instant: True`). You can invite individual users (`user-invite`), entire roles (`role-invite`), add external guest emails (`external-emails`), and specify duration (`15/30/45m`) with custom meeting notes. The scheduler routes automatically to Cal.com.
3. **Auto-VC and Recording**: For Discord `location-type`, the bot creates a temporary voice channel in the **EVENTS** category 5 minutes before start (or instantly) and pings invitees via DM. It automatically starts audio recording.
4. **External Sync & Portal**: Web scheduler portal (cal.gobitsnbytes.org) supports responsive mobile booking, multi-host scheduling, custom favicons, and a redesigned availability dashboard with toggle switches, bulk actions, and copy-to-all rows.
5. **AI Transcript**: After a recorded meeting ends, the bot processes the audio, saving an AI-generated meeting summary, key decisions, action items (with assignees), and the full timestamped transcript. Access it via `/meet-transcript view meeting-id:<id>`. Use `/meet-transcript list` or `/meet-transcript search query:<term>` to find past transcripts.

6. Dynamic Action-Item Tracker: Automatically extracts action items (task details, assignees, deadlines) from Gemini-generated meeting briefs. Employs a multi-layer fuzzy matcher to resolve assignee names to Discord Snowflake IDs via voice timeline maps, attendee lists, and guild searches, then dispatches interactive DM alerts with "Mark Completed" and "Dismiss" buttons connected to a local SQLite/Turso database.

7. Rescheduling & Multi-Channel Alerts: Allows either the host or guest to reschedule booked syncs up to 3 times directly from the landing page. Reschedule requests enforce availability checks and trigger real-time multi-channel notifications (Web Push, Discord DMs, and SMTP email alerts).

8. Contributor Instant Meeting Launcher: Authenticated contributors can spin up "Open" or "Invite-only" temporary voice sessions directly from the portal homepage, automatically provisioning Discord VCs and sending join alerts to invitees.

9. Voice Recording Consent Notices: Automatically plays spoken recording disclosures in English and Hindi when users join the VC, and broadcasts matching interactive text warnings with language translation toggle buttons in the VC text chat.

10. Recorder Resilience & Debounce: Integrates a 2-minute empty voice channel debounce to prevent premature cleanup and automatically reconnects recording bots when humans join/remain in the VC (maintaining the 2-human requirement).

## 🌱 Fork Onboarding & Lifecycle Rules

- **Onboarding Journey**: Complete 7 structural steps: 1. Join GitHub -> 2. Create fork channel -> 3. Deploy website -> 4. Share Notion -> 5. First pulse -> 6. Define team -> 7. Plan first event. Completed milestones are tracked via `/onboarding-status`.
- **Stale Detection**: The bot runs a weekly stale detector. If a chapter has no `/pulse` update for 60-89 days, the lead is warned in `#leads-council`. At 90+ days without a pulse, an alert goes to staff in `#team-forks` for archiving.
- **Health Score**: Calculated dynamically (0-100) based on pulse consistency, events count, reports, and team completeness.
- **Points & Badges**: Earned by executing activities. View ranks via `/leaderboard` and badges via `/fork-badges`.

# 📋 Commands Reference Dictionary

- 👤 Fork Leads Commands
    - `/fork-request`: Initialize a new B&B node application.
    - `/pulse city:<city> update:<text>`: Submit a quick text update detailing current branch progress.
    - `/fork-status city:<city>`: View a complete operational health dashboard for your city.
    - `/meet-email [set/remove/status]`: Manage registered email configuration for meetings.
    - `/meet-schedule title:<title> location-type:<vc/external> [options]`: Book a meeting with automatic VC/Email/Cal.com provisioning.
    - `/meet-transcript [view/list/search]`: List, search, or view AI meeting summaries and transcripts.
    - `/event-create title:<title> city:<city> date:<date> type:<type> description:<text>`: Propose and queue a new event for chapter approval.
    - `/event-update event-id:<id> [status] [date] [attendees]`: Update event statuses, date, and final attendee metrics.
    - `/report-submit city:<city> type:<type> [notes] [attachment]`: Submit monthly/bi-weekly reports with PDF/attachment URLs.
    - `/team-view [city]`: View your team's configuration.
    - `/team-update city:<city> member:<user> role:<role> action:<add/remove>`: Add or remove team members and assign leads.
    - /meet-start meet-code:<code>: Manually start a meeting, notify missing invitees via DM, and start recording immediately.
- 🛡️ Staff & Admin Commands
    - `/admin-add-lead user:<user> city:<city>`: Onboard a fork lead directly, skipping application reviews.
    - `/merge user:<user> city:<city>`: Officially merge a pending fork lead and approve their chapter.
    - `/onboarding-complete city:<city> steps:<step(s)>`: Mark a specific onboarding checklist step complete.
    - `/onboarding-status [city]`: Check onboarding checkpoints for pending/active chapters.
    - `/archive city:<city> reason:<text>`: Archive an inactive fork chapter with a specified reason.
    - `/forks`: View technical topology and connections of all nodes.
    - `/forks-info`: Post or update a single embed listing all active and pending forks info.
    - `/report-status [city]`: View outstanding reports status for all nodes.
    - `/meet-transcript delete meeting-id:<id>`: Purge an outdated or sensitive meeting transcript.
    - `/ping [test-email]` & `/system-test [test-email]`: Perform latency tests and test SMTP email dispatch.
- 🌐 Public & Utility Commands
    - `/event-calendar`: View active network event schedule.
    - `/ping`: Show latency statistics.
    - `/help`: Display general help card.
    - `/leaderboard [period]`: Show top chapters by points leaderboard.
    - `/fork-health [city] [period]`: View health leaderboard for all active chapters.
    - `/fork-badges [city]`: Show badges earned by a city chapter.
    - `/view-forks`: View technical topology of the bits&bytes™ network.
