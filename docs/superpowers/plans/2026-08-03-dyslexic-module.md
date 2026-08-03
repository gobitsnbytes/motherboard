# Dyslexic Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Dyslexic — an internal sponsorship and outreach module inside Motherboard where volunteers add companies, get AI research, generate sponsor emails, log sends without duplicating each other's outreach, and track follow-ups and contributions.

**Architecture:** A core module built exactly like Meetings/IAM/Finance — SQLAlchemy models in the shared `models.py`, one Alembic revision, one router at `/api/dyslexic`, Pydantic v2 schemas, and Next.js App Router pages under `/dashboard/dyslexic` inside the existing `DashboardShell`. It reuses Discord auth, the HMAC-signing catch-all proxy, the audit log, and the Redis event bus untouched. The only new plumbing is an SSE hub bridging the event bus to the browser, plus a streaming branch in the Next proxy.

**Tech Stack:** FastAPI 0.111+, Pydantic v2, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16 (aiosqlite in tests), Redis pub/sub, `google-genai` with `gemini-3.6-flash`, Next.js 15 App Router, React 19, `@bnb/ui`, Tailwind.

**Design spec:** `docs/superpowers/specs/2026-08-03-dyslexic-design.md`. Read it before Task 1.

## Global Constraints

- Backend commands run with `uv` from `apps/api`. Never add Bun/Node tooling there. Frontend uses `bun`.
- Python 3.12, SQLAlchemy 2.0.51 — confirmed installed. `sqlite_where` and `postgresql_where` both compile partial indexes; verified.
- **No `dyslexic.*` permission keys.** Nothing is added to `CORE_PERMISSIONS`. Every route depends on `CurrentUserDep` and nothing further. Any logged-in user has full access.
- **No hard delete.** Companies and contacts archive via `is_archived`. No `DELETE` route for either.
- Every mutation writes a `dyslexic_events` row AND an `audit_log` entry in the same transaction.
- `write_audit_entry` does not commit. The caller owns the transaction.
- `event_bus.publish` is called **after** commit, never before.
- Model ID is `gemini-3.6-flash`, read from the new `DYSLEXIC_GEMINI_MODEL` setting. Do not change the existing `gemini_model` setting — Meetings depends on it.
- Gemini 3.6 rejects `temperature`, `top_p`, `top_k`, `candidate_count`; `thinking_budget` is replaced by a `thinking_level` string. Do not copy the 2.5-era call shape from `meetings.py` verbatim.
- Brand copy: **bits&bytes** always lowercase with the ampersand. `GOBITSNBYTES FOUNDATION` only for legal entity references. Never "Bits & Bytes", "B&B", or "bits and bytes".
- UI must use `@bnb/ui` components and existing tokens (`border-2 border-border`, `rounded-base`, `bg-[#111]`, `font-heading`). `sidebar`, `form`, and `resizable` are NOT exported from `@bnb/ui` — do not import them.
- Follow-up interval is the constant `FOLLOW_UP_INTERVAL_DAYS = 3`. Claim window is `CLAIM_MINUTES = 30`.
- Invariant: **a contact has at most one pending follow-up**, and **at most one `initial` outreach row**.
- The Gemini client is never called in tests. All model access goes through a seam that tests substitute.

---

## File Structure

**Backend — create:**

| File | Responsibility |
| --- | --- |
| `apps/api/app/dyslexic/__init__.py` | package marker, exports constants |
| `apps/api/app/dyslexic/constants.py` | stage order, statuses, outcomes, weights, intervals |
| `apps/api/app/dyslexic/service.py` | transactional workflow ops (claim, log_send, record_outcome, stage advance, timeline+audit writes) |
| `apps/api/app/dyslexic/research.py` | grounded company research; the mockable AI seam |
| `apps/api/app/dyslexic/emails.py` | draft generation; the second AI seam |
| `apps/api/app/dyslexic/stats.py` | dashboard counters and leaderboard aggregates |
| `apps/api/app/schemas/dyslexic.py` | Pydantic v2 request/response models |
| `apps/api/app/routers/dyslexic.py` | HTTP surface only — thin, delegates to service |
| `apps/api/app/events/sse.py` | `SseHub`, generic, not Dyslexic-specific |
| `apps/api/alembic/versions/<rev>_add_dyslexic_tables.py` | schema migration |
| `apps/api/tests/test_dyslexic_companies.py` | company CRUD, dedupe |
| `apps/api/tests/test_dyslexic_contacts.py` | contact CRUD, claims |
| `apps/api/tests/test_dyslexic_outreach.py` | the core guarantees |
| `apps/api/tests/test_dyslexic_stats.py` | aggregates |
| `apps/api/tests/test_dyslexic_research.py` | AI seam, mocked |

**Backend — modify:** `app/db/models.py` (six models), `app/main.py` (include router), `app/config.py` (one setting).

**Frontend — create:** `app/dashboard/dyslexic/{page,companies/page,companies/[id]/page,contacts/page,leaderboard/page}.tsx`, `components/dyslexic/*`, `lib/dyslexic.ts`, `hooks/useDyslexicStream.ts`.

**Frontend — modify:** `components/dashboard/Sidebar.tsx` (one nav entry), `app/api/[...path]/route.ts` (stream passthrough).

Service logic lives in `service.py`, not in the router. The router validates and delegates. This keeps the transactional guarantees in one testable place instead of spread across handlers.

---

### Task 1: Schema — six models and the migration

**Files:**
- Modify: `apps/api/app/db/models.py` (append after `BotSetting`)
- Create: `apps/api/app/dyslexic/__init__.py`, `apps/api/app/dyslexic/constants.py`
- Create: `apps/api/alembic/versions/<rev>_add_dyslexic_tables.py` (generated)
- Test: `apps/api/tests/test_dyslexic_schema.py`

**Interfaces:**
- Produces: `DyslexicCompany`, `DyslexicContact`, `DyslexicEmail`, `DyslexicOutreach`, `DyslexicFollowUp`, `DyslexicEvent` importable from `app.db.models`. Constants `COMPANY_STAGES`, `FOLLOW_UP_INTERVAL_DAYS`, `CLAIM_MINUTES`, `LEADERBOARD_WEIGHTS` from `app.dyslexic.constants`.

- [ ] **Step 1: Write the constants module**

Create `apps/api/app/dyslexic/constants.py`:

```python
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
    "replied": "replied",
    "meeting_scheduled": "meeting",
    "sponsored": "sponsored",
    "rejected": "rejected",
    "follow_up_sent": "follow_up",
}

# Outcome → contact status.
OUTCOME_CONTACT_STATUS_MAP: dict[str, str] = {
    "no_reply": "no_reply",
    "replied": "replied",
    "meeting_scheduled": "meeting_scheduled",
    "sponsored": "sponsored",
    "rejected": "rejected",
    "follow_up_sent": "contacted",
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
```

Create `apps/api/app/dyslexic/__init__.py`:

```python
"""Dyslexic — sponsorship and outreach module."""
```

- [ ] **Step 2: Write the failing schema test**

Create `apps/api/tests/test_dyslexic_schema.py`:

```python
"""Schema-level guarantees for the Dyslexic tables."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicOutreach,
    User,
)
from tests.conftest import TestingSessionLocal


@pytest_asyncio.fixture
async def seeded():
    """A user, a company, and a contact to hang outreach off."""
    async with TestingSessionLocal() as session:
        user = User(display_name="Test Volunteer", email="v@example.com")
        session.add(user)
        await session.flush()

        company = DyslexicCompany(
            name="Zomato", website="https://zomato.com",
            normalized_domain="zomato.com", added_by=user.id,
        )
        session.add(company)
        await session.flush()

        contact = DyslexicContact(
            company_id=company.id, name="Priya Sharma",
            email="priya@zomato.com", added_by=user.id,
        )
        session.add(contact)
        await session.commit()
        return {"user_id": user.id, "company_id": company.id, "contact_id": contact.id}


@pytest.mark.asyncio
async def test_normalized_domain_is_unique(seeded):
    """Two volunteers cannot add the same company twice."""
    async with TestingSessionLocal() as session:
        session.add(DyslexicCompany(
            name="Zomato Duplicate", website="https://www.zomato.com/careers",
            normalized_domain="zomato.com", added_by=seeded["user_id"],
        ))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_same_email_twice_at_one_company_is_rejected(seeded):
    async with TestingSessionLocal() as session:
        session.add(DyslexicContact(
            company_id=seeded["company_id"], name="Priya S (dupe)",
            email="priya@zomato.com", added_by=seeded["user_id"],
        ))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_contacts_without_email_do_not_collide(seeded):
    """NULL emails are distinct — several unknown-address contacts are fine."""
    async with TestingSessionLocal() as session:
        session.add(DyslexicContact(
            company_id=seeded["company_id"], name="Unknown One",
            email=None, added_by=seeded["user_id"],
        ))
        session.add(DyslexicContact(
            company_id=seeded["company_id"], name="Unknown Two",
            email=None, added_by=seeded["user_id"],
        ))
        await session.commit()


@pytest.mark.asyncio
async def test_partial_index_blocks_a_second_initial_outreach(seeded):
    """The duplicate-outreach guarantee, enforced by the database itself."""
    now = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        session.add(DyslexicOutreach(
            contact_id=seeded["contact_id"], company_id=seeded["company_id"],
            kind="initial", sent_by=seeded["user_id"], sent_at=now,
        ))
        await session.commit()

    async with TestingSessionLocal() as session:
        session.add(DyslexicOutreach(
            contact_id=seeded["contact_id"], company_id=seeded["company_id"],
            kind="initial", sent_by=seeded["user_id"], sent_at=now + timedelta(hours=1),
        ))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_multiple_follow_ups_are_allowed(seeded):
    """A contact can be chased more than once — only `initial` is capped."""
    now = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        for offset in (1, 2):
            session.add(DyslexicOutreach(
                contact_id=seeded["contact_id"], company_id=seeded["company_id"],
                kind="follow_up", sent_by=seeded["user_id"],
                sent_at=now + timedelta(days=offset),
            ))
        await session.commit()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_dyslexic_schema.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'DyslexicCompany' from 'app.db.models'`

- [ ] **Step 4: Add the six models**

Append to `apps/api/app/db/models.py`. Note `text` must be added to the `sqlalchemy` import block at the top of the file.

```python
# ---------------------------------------------------------------------------
# Dyslexic — Sponsorship & Outreach
# ---------------------------------------------------------------------------

class DyslexicCompany(Base):
    """A prospective sponsor. Research is AI-generated and advisory only."""

    __tablename__ = "dyslexic_companies"
    __table_args__ = (
        Index("ix_dyslexic_companies_stage", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Lowercased, scheme/www/path stripped. Unique so the same sponsor can't
    # be added twice. Null when no website was supplied.
    normalized_domain: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(30), default="research", nullable=False)
    research_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    research_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    # Model output kept verbatim when JSON parsing fails, so a bad response is
    # debuggable instead of lost.
    research_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    research_model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    fork_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forks.id", ondelete="SET NULL"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    contacts: Mapped[list["DyslexicContact"]] = relationship(
        "DyslexicContact", back_populates="company", cascade="all, delete-orphan"
    )
    adder: Mapped["User | None"] = relationship("User", foreign_keys=[added_by])

    def __repr__(self) -> str:
        return f"<DyslexicCompany name={self.name!r} stage={self.stage!r}>"


class DyslexicContact(Base):
    """A person at a prospective sponsor, and the outreach state for them."""

    __tablename__ = "dyslexic_contacts"
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_dyslexic_contact_company_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Always stored lowercased so uniqueness is case-insensitive in practice.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
    # Set once at the first send and never overwritten — this is the record of
    # who owns this outreach.
    contacted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Soft claim while drafting. Expires on its own; no cleanup job.
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    company: Mapped["DyslexicCompany"] = relationship(
        "DyslexicCompany", back_populates="contacts"
    )
    contacter: Mapped["User | None"] = relationship("User", foreign_keys=[contacted_by])
    claimer: Mapped["User | None"] = relationship("User", foreign_keys=[claimed_by])
    adder: Mapped["User | None"] = relationship("User", foreign_keys=[added_by])

    def __repr__(self) -> str:
        return f"<DyslexicContact name={self.name!r} status={self.status!r}>"


class DyslexicEmail(Base):
    """A generated draft. Kept whether or not it was ever sent."""

    __tablename__ = "dyslexic_emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_contacts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), default="initial", nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extra_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DyslexicEmail contact={self.contact_id} kind={self.kind!r}>"


class DyslexicOutreach(Base):
    """One 'I've Sent Email' click. The duplicate guard lives here."""

    __tablename__ = "dyslexic_outreach"
    __table_args__ = (
        # At most one initial email per contact, enforced by the database so a
        # race between two volunteers cannot produce two.
        Index(
            "uq_dyslexic_outreach_initial_per_contact",
            "contact_id",
            unique=True,
            postgresql_where=text("kind = 'initial'"),
            sqlite_where=text("kind = 'initial'"),
        ),
        Index("ix_dyslexic_outreach_sent_by_kind", "sent_by", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_contacts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Null when the volunteer wrote the email themselves instead of generating.
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_emails.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(20), default="initial", nullable=False)
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    outcome_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outcome_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DyslexicOutreach contact={self.contact_id} kind={self.kind!r}>"


class DyslexicFollowUp(Base):
    """A reminder to chase. At most one pending per contact."""

    __tablename__ = "dyslexic_follow_ups"
    __table_args__ = (
        Index("ix_dyslexic_follow_ups_assignee_due", "assigned_to", "status", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    outreach_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_outreach.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_contacts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DyslexicFollowUp contact={self.contact_id} due={self.due_at}>"


class DyslexicEvent(Base):
    """Per-company product timeline. Distinct from audit_log, which stays a
    platform-wide forensic record indexed by action rather than by company."""

    __tablename__ = "dyslexic_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dyslexic_contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, name="metadata", default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped["User | None"] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<DyslexicEvent kind={self.kind!r} company={self.company_id}>"
```

Add `text` to the existing `from sqlalchemy import (...)` block at the top of `models.py`.

- [ ] **Step 5: Run the schema test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_dyslexic_schema.py -v`
Expected: 5 passed. If `test_partial_index_blocks_a_second_initial_outreach` fails, the partial index did not make it into `Base.metadata` — check the `__table_args__` tuple has a trailing comma.

- [ ] **Step 6: Generate and inspect the migration**

Run: `cd apps/api && uv run alembic revision --autogenerate -m "add dyslexic tables"`

Open the generated file and verify it creates six tables and that the partial index carries `postgresql_where`. Autogenerate sometimes drops the `where` clause — if it did, add it by hand:

```python
op.create_index(
    "uq_dyslexic_outreach_initial_per_contact",
    "dyslexic_outreach", ["contact_id"], unique=True,
    postgresql_where=sa.text("kind = 'initial'"),
)
```

Also confirm the revision does **not** contain drops for unrelated tables. If it does, the autogenerate compared against a stale database — reset and regenerate.

- [ ] **Step 7: Verify the migration applies and rolls back**

Run: `cd apps/api && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: three clean runs, no errors.

- [ ] **Step 8: Run the full suite to confirm nothing regressed**

Run: `cd apps/api && uv run pytest -q`
Expected: all previously-passing tests still pass, plus the 5 new ones.

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/db/models.py apps/api/app/dyslexic/ apps/api/alembic/versions/ apps/api/tests/test_dyslexic_schema.py
git commit -m "feat(dyslexic): add schema for companies, contacts, emails, outreach, follow-ups, timeline"
```

---

### Task 2: Service layer — the workflow guarantees

**Files:**
- Create: `apps/api/app/dyslexic/service.py`
- Test: `apps/api/tests/test_dyslexic_outreach.py`

**Interfaces:**
- Consumes: models and constants from Task 1.
- Produces, all `async` and all taking `db: AsyncSession` first:
  - `normalize_domain(website: str | None) -> str | None`
  - `record_event(db, *, company_id, actor_id, kind, summary, contact_id=None, metadata=None) -> DyslexicEvent`
  - `claim_contact(db, *, contact_id, user_id) -> DyslexicContact` — raises `ClaimConflict`
  - `release_claim(db, *, contact_id, user_id) -> None`
  - `log_send(db, *, contact_id, user_id, kind, email_id=None) -> DyslexicOutreach` — raises `AlreadyContacted`
  - `record_outcome(db, *, outreach_id, user_id, outcome, note=None) -> DyslexicOutreach`
  - `resolve_follow_up(db, *, follow_up_id, user_id, note=None) -> DyslexicFollowUp`
  - Exceptions `ClaimConflict`, `AlreadyContacted`, `NotFound` each carrying `.detail: dict`
- None of these commit. The router owns the transaction and publishes events after commit.

- [ ] **Step 1: Write the failing tests for the core guarantees**

Create `apps/api/tests/test_dyslexic_outreach.py` covering, with real assertions rather than smoke checks:

1. `test_log_send_creates_outreach_contact_state_and_follow_up` — one call produces one outreach row, sets `contacted_by`/`contacted_at`/`status="contacted"`, advances company stage to `email_sent`, creates exactly one `pending` follow-up due `FOLLOW_UP_INTERVAL_DAYS` out assigned to the sender, and writes one `dyslexic_events` row of kind `email.sent`.
2. `test_second_initial_send_raises_already_contacted` — the second call raises `AlreadyContacted` whose `.detail` names the first sender's `display_name` and the date.
3. `test_follow_up_send_resolves_the_previous_follow_up` — after an initial send and then a `follow_up` send, the contact has exactly one `pending` follow-up and one `done` one.
4. `test_record_outcome_follow_up_sent_matches_log_send_path` — recording `follow_up_sent` on the initial outreach produces the same end state as calling `log_send(kind="follow_up")`: one new outreach row, one pending follow-up, one resolved.
5. `test_stage_never_moves_backwards` — a company at `meeting` stays at `meeting` after an initial send on a second contact.
6. `test_claim_conflict` — a second user claiming a held contact raises `ClaimConflict` naming the holder; after `claim_expires_at` is backdated, the claim succeeds.
7. `test_claim_is_released_by_log_send` — `claimed_by` is null after a send.

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_dyslexic_outreach.py -v`
Expected: FAIL at import — `app.dyslexic.service` does not exist.

- [ ] **Step 3: Implement `service.py`**

Key implementation notes the code must honour:

- `normalize_domain` lowercases, strips scheme, strips a leading `www.`, drops path/query/fragment and any trailing dot or slash. `None` in → `None` out. A bare `"zomato.com"` and `"https://www.zomato.com/careers?x=1"` both → `"zomato.com"`.
- `claim_contact` is a single conditional `UPDATE … WHERE id = :id AND (claimed_by IS NULL OR claimed_by = :me OR claim_expires_at < :now)` using `db.execute(update(...))`; `result.rowcount == 0` means conflict — re-read the row to name the holder in the exception.
- `log_send` does `select(DyslexicContact).where(...).with_for_update()` first, checks `contacted_at` when `kind == "initial"`, and lets the partial unique index be the backstop. Order of writes: outreach → contact state → company stage → resolve prior pending follow-up → create new follow-up → `record_event` → `write_audit_entry` → clear claim. No commit.
- `record_outcome` with `outcome == "follow_up_sent"` sets the outcome on the original row and then calls `log_send(kind="follow_up")` so both paths converge, per spec §5.3.
- Every write path calls both `record_event` and `write_audit_entry` (action `dyslexic.<kind>`, `target_type="dyslexic_company"`).

- [ ] **Step 4: Run to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_dyslexic_outreach.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/dyslexic/service.py apps/api/tests/test_dyslexic_outreach.py
git commit -m "feat(dyslexic): add service layer with duplicate-outreach and follow-up guarantees"
```

---

### Task 3: Schemas and router — companies and contacts

**Files:**
- Create: `apps/api/app/schemas/dyslexic.py`, `apps/api/app/routers/dyslexic.py`
- Modify: `apps/api/app/main.py` (import and `include_router`)
- Test: `apps/api/tests/test_dyslexic_companies.py`, `apps/api/tests/test_dyslexic_contacts.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2.
- Produces: the HTTP surface in spec §6.2–6.3. Router variable is `router = APIRouter(prefix="/api/dyslexic", tags=["dyslexic"])`.

Tests use the existing `conftest.py` HMAC signing helper — read `tests/test_finance_ledger.py` for the established pattern of building signed requests.

Coverage required: create company (201 + research queued), duplicate domain (409 with existing id), duplicate name when website is absent (409), list filters by stage and `q`, archive via PATCH, no `DELETE` route exists (405), contact create (201), per-company duplicate email (409), cross-company duplicate returns `duplicate_warning` in the body with 201, claim (200) and claim conflict (409).

Steps follow the same failing-test → run → implement → run → commit cycle.

---

### Task 4: Outreach, follow-up, and stats routes

**Files:**
- Modify: `apps/api/app/routers/dyslexic.py`, `apps/api/app/schemas/dyslexic.py`
- Create: `apps/api/app/dyslexic/stats.py`
- Test: `apps/api/tests/test_dyslexic_stats.py`, extend `test_dyslexic_outreach.py` with route-level tests

**Interfaces:**
- Produces: `GET /stats`, `GET /activity`, `GET /leaderboard`, `POST /contacts/{id}/sent`, `PATCH /outreach/{id}/outcome`, `GET /follow-ups`, `POST /follow-ups/{id}/resolve`.
- `stats.py` exposes `async def dashboard_stats(db, user_id) -> dict` and `async def leaderboard(db, period: str) -> list[dict]`.

Aggregates are the queries in spec §9, run as one grouped query joined to `users`, ordered by the weighted score from `LEADERBOARD_WEIGHTS`. Tests build fixtures by hand and assert exact counts, plus that `?period=30d` excludes older rows and that ordering follows the weights.

---

### Task 5: AI — research and email generation

**Files:**
- Create: `apps/api/app/dyslexic/research.py`, `apps/api/app/dyslexic/emails.py`
- Modify: `apps/api/app/config.py`, `.env.example`, `apps/api/app/routers/dyslexic.py`
- Test: `apps/api/tests/test_dyslexic_research.py`

**Interfaces:**
- Produces: `async def research_company(name, website) -> ResearchResult` and `async def generate_email(company, contact, kind, tone, extra_context, previous=None) -> DraftResult`, both routed through a module-level `_call_model` seam that tests monkeypatch. `ResearchResult` carries `ok: bool`, `data: dict`, `raw: str`, `error: str | None`, `model: str`.

Config addition:

```python
    # Dyslexic uses its own model setting so research and email generation can
    # move independently of the meeting transcription pipeline.
    dyslexic_gemini_model: str = Field(
        default="gemini-3.6-flash", validation_alias="DYSLEXIC_GEMINI_MODEL"
    )
```

Research runs as a FastAPI `BackgroundTask`, sets `research_status` `running` → `complete`/`failed`, writes a `research.generated` or `research.failed` timeline event, and publishes `dyslexic.research.completed`. The whole background function is wrapped so an unhandled exception can never leave a company stuck in `running`.

Test coverage, all with the model mocked: clean JSON parses; fenced ```json output parses; unparseable output sets `failed` and preserves `research_raw`; a missing API key sets `failed` with a clear message rather than raising; and a company whose research failed still accepts contacts and sends.

---

### Task 6: Live updates — SSE hub, stream route, proxy passthrough

**Files:**
- Create: `apps/api/app/events/sse.py`
- Modify: `apps/api/app/routers/dyslexic.py`, `apps/web/app/api/[...path]/route.ts`, `deploy/api/nginx.conf`
- Create: `apps/web/hooks/useDyslexicStream.ts`
- Test: `apps/api/tests/test_dyslexic_sse.py`

The proxy change is the part that silently breaks everything if missed. In `apps/web/app/api/[...path]/route.ts`, before the existing `arrayBuffer()` return:

```ts
  // Server-sent events must not be buffered — arrayBuffer() would wait for a
  // stream that never ends.
  const upstreamType = upstreamResponse.headers.get("content-type") ?? "";
  if (upstreamType.startsWith("text/event-stream")) {
    responseHeaders.set("Cache-Control", "no-cache, no-transform");
    responseHeaders.set("Connection", "keep-alive");
    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    });
  }
```

`nginx.conf` gets `proxy_buffering off;` and a raised `proxy_read_timeout` on the stream location — confirm first whether nginx is actually in front of this path in the deployed topology (spec §15).

---

### Task 7: Frontend — shell, dashboard, companies

**Files:**
- Modify: `apps/web/components/dashboard/Sidebar.tsx`
- Create: `apps/web/lib/dyslexic.ts`, `apps/web/app/dashboard/dyslexic/page.tsx`, `apps/web/app/dashboard/dyslexic/companies/page.tsx`, `apps/web/components/dyslexic/{DyslexicTabs,CompanyTable,AddCompanyDialog,ActivityFeed,FollowUpPanel}.tsx`

Sidebar gets one entry after Meetings:

```ts
  { label: "Dyslexic", href: "/dashboard/dyslexic", icon: Handshake },
```

with `Handshake` added to the `lucide-react` import. Everything else follows `MembersContent.tsx` for table markup and `StatCard.tsx` for tiles. No new design tokens, no inline-style shell.

---

### Task 8: Frontend — company detail, the outreach loop

**Files:**
- Create: `apps/web/app/dashboard/dyslexic/companies/[id]/page.tsx`, `apps/web/components/dyslexic/{ResearchPanel,ContactTable,AddContactDialog,GenerateEmailDialog,Timeline,OutcomeDialog}.tsx`

This is the page the module exists for. `GenerateEmailDialog` claims the contact on open, shows the editable draft, offers Copy, and the "I've Sent Email" button posts to `/sent` and surfaces a 409 as a readable message naming who already contacted them.

---

### Task 9: Frontend — contacts, leaderboard, and a live-collaboration check

**Files:**
- Create: `apps/web/app/dashboard/dyslexic/contacts/page.tsx`, `apps/web/app/dashboard/dyslexic/leaderboard/page.tsx`

Ends with the documented manual verification: two browser sessions, one claims a contact, the second sees the claim appear without refreshing and is refused the send with a clear message.

---

## Verification before calling this done

- `cd apps/api && uv run pytest -q` — all green, including the pre-existing suite.
- `bun run build` from the repo root — no TypeScript errors.
- The multi-tab collaboration check from Task 9, performed and observed.
- No `dyslexic.*` key anywhere in `seed_data.py`.
- `rg "DELETE" apps/api/app/routers/dyslexic.py` returns only claim release.
