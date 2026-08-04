"""Shared constants for the Dyslexic sponsorship outreach module."""

# Company pipeline stages, in order. Transitions are monotonic — a stage only
# advances, so logging a first email on one contact never pulls a company that
# already reached `meeting` back to `email_sent`.
COMPANY_STAGES: tuple[str, ...] = (
    "research",
    "contacts_added",
    "email_generated",
    "email_sent",
    "follow_up",
    "replied",
    "meeting",
    "negotiation",
    "sponsored",
    "rejected",
)

RESEARCH_STATUSES: tuple[str, ...] = ("pending", "running", "complete", "failed")

CONTACT_STATUSES: tuple[str, ...] = (
    "new",
    "contacted",
    "no_reply",
    "replied",
    "meeting_scheduled",
    "sponsored",
    "rejected",
    "bounced",
)

OUTREACH_KINDS: tuple[str, ...] = ("initial", "follow_up")

OUTREACH_OUTCOMES: tuple[str, ...] = (
    "follow_up_sent",
    "no_reply",
    "replied",
    "meeting_scheduled",
    "sponsored",
    "rejected",
)

FOLLOW_UP_STATUSES: tuple[str, ...] = ("pending", "done", "cancelled")

# Outcome → company stage. Outcomes not listed do not move the pipeline.
OUTCOME_STAGE_MAP: dict[str, str] = {
    "follow_up_sent": "follow_up",
    "replied": "replied",
    "meeting_scheduled": "meeting",
    "sponsored": "sponsored",
    "rejected": "rejected",
}

# Outcome → contact status.
OUTCOME_CONTACT_STATUS_MAP: dict[str, str] = {
    "follow_up_sent": "contacted",
    "no_reply": "no_reply",
    "replied": "replied",
    "meeting_scheduled": "meeting_scheduled",
    "sponsored": "sponsored",
    "rejected": "rejected",
}

FOLLOW_UP_INTERVAL_DAYS = 3
CLAIM_MINUTES = 30

# Ranking rewards outcomes over volume — fifty junk companies must not
# outrank one closed sponsor.
LEADERBOARD_WEIGHTS: dict[str, int] = {
    "companies_added": 1,
    "contacts_added": 1,
    "emails_sent": 3,
    "follow_ups_sent": 2,
    "replies_received": 5,
    "meetings_scheduled": 8,
    "sponsors_closed": 20,
}


def stage_index(stage: str) -> int:
    """Position of a stage in the pipeline; -1 if unknown."""
    try:
        return COMPANY_STAGES.index(stage)
    except ValueError:
        return -1


def advance_stage(current: str, candidate: str) -> str:
    """Return whichever stage is further along. Never moves backwards."""
    return candidate if stage_index(candidate) > stage_index(current) else current
