"""FastAPI router for Meetings, Scheduling, and Transcript Handling."""

import json
import logging
import time
import os
import tempfile
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, BackgroundTasks
from sqlalchemy import select, update, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession, get_current_user
from app.iam.principal import ResolvedPrincipal
from app.iam.policy import require_permission
from app.config import get_settings, Settings
from app.db.models import (
    BotMeeting,
    MeetingAttendee,
    MeetingTranscript,
    ActionItem,
    UserAvailability,
    MeetingEmailPreference,
    MeetingRescheduleHistory,
    User,
    DiscordAccount
)
from app.schemas.meetings import (
    MeetingCreate,
    MeetingUpdate,
    MeetingOut,
    MeetingAttendeeSchema,
    MeetingTranscriptSchema,
    UserAvailabilitySchema,
    UserAvailabilityUpdate,
    MeetingEmailPreferenceSchema,
    MeetingEmailPreferenceUpdate,
    ActionItemSchema,
    ActionItemCreate,
    ActionItemStatusUpdate,
    SpeakingTimelineItem
)
from app.provisioning.client import DiscordClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meetings", tags=["meetings"])

# ---------------------------------------------------------------------------
# ICS and Email Notification Helpers (Unified in Python)
# ---------------------------------------------------------------------------

def generate_ics(meeting_id: str, title: str, start_time_ms: int, end_time_ms: int, description: str, location: str, organizer_email: str = "gobitsnbytes@gmail.com", attendee_emails: List[str] = None) -> str:
    """Generate a valid, minimal iCalendar (.ics) request body."""
    dt_start = datetime.datetime.fromtimestamp(start_time_ms / 1000, tz=datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dt_end = datetime.datetime.fromtimestamp(end_time_ms / 1000, tz=datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dt_stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    attendee_lines = []
    if attendee_emails:
        for email in attendee_emails:
            attendee_lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN=\"{email}\":mailto:{email}")
    attendee_str = "\n".join(attendee_lines)
    attendee_block = f"\n{attendee_str}" if attendee_str else ""
    
    desc_escaped = (description or "").replace("\r\n", "\\n").replace("\n", "\\n")
    
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Bits and Bytes Foundation//Motherboard//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{meeting_id}@gobitsnbytes.org
DTSTAMP:{dt_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{title}
DESCRIPTION:{desc_escaped}
LOCATION:{location or 'Discord VC'}
ORGANIZER;CN="bits&bytes™":mailto:{organizer_email}{attendee_block}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""


def get_invite_html(title: str, formatted_time: str, vc_link: str, description: Optional[str]) -> str:
    desc_html = f"<p><strong>Description:</strong> {description}</p>" if description else ""
    content_html = f"""
    <h2>You have been invited to a meeting!</h2>
    <div class="card">
        <h3 class="card-title">{title}</h3>
        <div class="detail-row">
            <span class="detail-label">When:</span>
            <span class="detail-value">{formatted_time}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Where:</span>
            <span class="detail-value"><a href="{vc_link}" style="color: #ff7a1b; text-decoration: underline;">{vc_link}</a></span>
        </div>
        {desc_html}
    </div>
    <div style="text-align: center; margin-top: 30px;">
        <a href="{vc_link}" class="btn">Join Meeting</a>
    </div>
    """
    return get_base_email_html(content_html, "Meeting Invitation")


def get_cancel_html(title: str, formatted_time: str) -> str:
    content_html = f"""
    <h2 style="color: #97192c;">Meeting Cancelled</h2>
    <div class="card" style="border-color: rgba(151, 25, 44, 0.4);">
        <h3 class="card-title" style="text-decoration: line-through; color: rgba(247, 241, 236, 0.6);">{title}</h3>
        <div class="detail-row">
            <span class="detail-label">Original Time:</span>
            <span class="detail-value">{formatted_time}</span>
        </div>
    </div>
    <p>This scheduled meeting has been cancelled. If this is an error, please contact the coordinator.</p>
    """
    return get_base_email_html(content_html, "Meeting Cancelled")


def get_reschedule_html(title: str, old_time: str, new_time: str, reason: str, rescheduled_by: str, vc_link: str) -> str:
    content_html = f"""
    <h2>Meeting Rescheduled</h2>
    <div class="card">
        <h3 class="card-title">{title}</h3>
        <div class="detail-row">
            <span class="detail-label">Previous Time:</span>
            <span class="detail-value" style="text-decoration: line-through; color: rgba(247, 241, 236, 0.6);">{old_time}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">New Time:</span>
            <span class="detail-value" style="color: #ff7a1b; font-weight: bold;">{new_time}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Rescheduled By:</span>
            <span class="detail-value">{rescheduled_by}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Reason:</span>
            <span class="detail-value"><em>{reason}</em></span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Where:</span>
            <span class="detail-value"><a href="{vc_link}" style="color: #ff7a1b; text-decoration: underline;">{vc_link}</a></span>
        </div>
    </div>
    <div style="text-align: center; margin-top: 30px;">
        <a href="{vc_link}" class="btn">Join Meeting</a>
    </div>
    """
    return get_base_email_html(content_html, "Meeting Rescheduled")


def get_base_email_html(content_html: str, title: str = "BITS&BYTES PROTOCOL") -> str:
    """Base dark-themed HTML shell matching brand guidelines."""
    return f"""
    <html>
    <head>
        <style>
            body {{
                background-color: #080504;
                color: #f7f1ec;
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                -webkit-font-smoothing: antialiased;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #120f0a;
                border: 1px solid rgba(247, 241, 236, 0.12);
                border-radius: 18px;
                overflow: hidden;
                box-shadow: 0 20px 60px rgba(7, 3, 2, 0.55);
            }}
            .header {{
                background-color: #120f0a;
                padding: 24px;
                text-align: center;
                border-bottom: 2px solid #97192c;
            }}
            .header h1 {{
                color: #ff7a1b;
                font-size: 20px;
                font-weight: 700;
                letter-spacing: 2px;
                margin: 0;
                text-transform: uppercase;
            }}
            .content {{
                padding: 32px 24px;
                color: #f7f1ec;
            }}
            .card {{
                background-color: rgba(20, 15, 10, 0.86);
                border: 1px solid rgba(247, 241, 236, 0.12);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 24px;
            }}
            .card-title {{
                font-size: 18px;
                font-weight: 600;
                color: #f8f2ed;
                margin-top: 0;
                margin-bottom: 12px;
            }}
            .detail-row {{
                margin-bottom: 12px;
                font-size: 14px;
            }}
            .detail-label {{
                color: #ff7a1b;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 12px;
                letter-spacing: 1px;
                display: inline-block;
                width: 120px;
            }}
            .detail-value {{
                color: #f7f1ec;
            }}
            .btn {{
                background-color: #97192c;
                color: #fff9f4 !important;
                text-decoration: none;
                padding: 12px 28px;
                font-weight: 700;
                border-radius: 12px;
                font-size: 14px;
                display: inline-block;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .footer {{
                background-color: #0c0906;
                padding: 20px;
                text-align: center;
                font-size: 11px;
                color: rgba(247, 241, 236, 0.4);
                border-top: 1px solid rgba(247, 241, 236, 0.06);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                {content_html}
            </div>
            <div class="footer">
                This is an automated operational transmission from the Bits&Bytes Motherboard.<br/>
                &copy; {datetime.datetime.now().year} GOBITSNBYTES FOUNDATION. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """


def send_smtp_email(settings: Settings, to_emails: List[str], subject: str, html_body: str, ics_content: Optional[str] = None, filename: str = "invite.ics"):
    """Send SMTP email containing HTML and optional iCalendar attachment."""
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        logger.warning("[SMTP] SMTP mailer not configured. Skipping email dispatch.")
        return

    # Root container is mixed to support files/attachments
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to_emails)

    # Alternative container holds the HTML version and the inline calendar invite
    alt_part = MIMEMultipart("alternative")
    
    # 1. Attach HTML body
    body_part = MIMEText(html_body, "html")
    alt_part.attach(body_part)

    # 2. Attach inline iCal REQUEST part to alternative (enables interactive RSVP buttons in Gmail/Outlook)
    if ics_content:
        cal_inline = MIMEBase("text", "calendar", method="REQUEST", charset="UTF-8")
        cal_inline.set_payload(ics_content.encode("utf-8"))
        cal_inline.add_header("Content-Class", "urn:content-classes:calendarmessage")
        cal_inline.add_header("Content-Transfer-Encoding", "8bit")
        alt_part.attach(cal_inline)

    msg.attach(alt_part)

    # 3. Attach downloadable .ics attachment (enables opening file directly in other calendar clients)
    if ics_content:
        part = MIMEBase("text", "calendar", method="REQUEST")
        part.set_payload(ics_content.encode("utf-8"))
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        part.add_header("Content-Class", "urn:content-classes:calendarmessage")
        part.add_header("Content-Transfer-Encoding", "base64")
        import email.encoders
        email.encoders.encode_base64(part)
        msg.attach(part)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_from, to_emails, msg.as_string())
        logger.info("[SMTP] Email successfully dispatched to: %s", to_emails)
    except Exception as e:
        logger.error("[SMTP] Failed to send email to %s: %s", to_emails, e)


async def resolve_emails_for_attendees(db: AsyncSession, settings: Settings, attendees: List[MeetingAttendee]) -> List[str]:
    """Resolves email addresses for direct and role-based attendees."""
    emails = []
    
    # 1. Direct user attendees (discord_ids)
    direct_discord_ids = [a.discord_id for a in attendees if a.attendee_type == "user"]
    if direct_discord_ids:
        # Check users table through Discord accounts
        stmt = (
            select(User.email)
            .join(DiscordAccount, User.id == DiscordAccount.user_id)
            .where(DiscordAccount.discord_id.in_(direct_discord_ids))
        )
        res = await db.execute(stmt)
        emails.extend([email for email in res.scalars().all() if email])

        # Also fallback/check user_availability table
        stmt_avail = select(UserAvailability.email).where(UserAvailability.discord_id.in_(direct_discord_ids))
        res_avail = await db.execute(stmt_avail)
        emails.extend([email for email in res_avail.scalars().all() if email])

        # Check preferences table
        stmt_pref = select(MeetingEmailPreference.email).where(MeetingEmailPreference.discord_id.in_(direct_discord_ids))
        res_pref = await db.execute(stmt_pref)
        emails.extend([email for email in res_pref.scalars().all() if email])

    # 2. Role-based attendees (need to call Discord API via bot token)
    role_discord_ids = [a.discord_id for a in attendees if a.attendee_type == "role"]
    if role_discord_ids and settings.discord_bot_token and settings.discord_guild_id:
        try:
            client = DiscordClient(settings.discord_bot_token)
            members = await client.get_guild_members(settings.discord_guild_id)
            matched_member_ids = []
            for m in members:
                roles = m.get("roles", [])
                if any(r_id in roles for r_id in role_discord_ids):
                    matched_member_ids.append(m["user"]["id"])
            
            if matched_member_ids:
                stmt_role_users = (
                    select(User.email)
                    .join(DiscordAccount, User.id == DiscordAccount.user_id)
                    .where(DiscordAccount.discord_id.in_(matched_member_ids))
                )
                res_role_users = await db.execute(stmt_role_users)
                emails.extend([email for email in res_role_users.scalars().all() if email])

                stmt_role_avail = select(UserAvailability.email).where(UserAvailability.discord_id.in_(matched_member_ids))
                res_role_avail = await db.execute(stmt_role_avail)
                emails.extend([email for email in res_role_avail.scalars().all() if email])
        except Exception as e:
            logger.error("[MEETING_EMAIL] Failed to resolve role members: %s", e)

    # Deduplicate emails
    return list(set(emails))


async def send_meeting_emails_task(meeting_id: str, email_type: str, settings: Settings, db_session_maker: Any, reschedule_reason: Optional[str] = None, rescheduled_by: Optional[str] = None):
    """Background task to resolve attendees and dispatch emails."""
    async with db_session_maker() as db:
        meeting_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
        res = await db.execute(meeting_stmt)
        meeting = res.scalar_one_or_none()
        if not meeting:
            return

        attendees_stmt = select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
        res_att = await db.execute(attendees_stmt)
        attendees = res_att.scalars().all()

        to_emails = await resolve_emails_for_attendees(db, settings, list(attendees))
        
        # Add external emails
        if meeting.external_emails:
            for email in meeting.external_emails.split(","):
                clean = email.strip()
                if clean and clean not in to_emails:
                    to_emails.append(clean)

        if not to_emails:
            logger.info("[MEETING_EMAIL] No emails found to notify for meeting %s", meeting.id)
            return

        formatted_time = datetime.datetime.fromtimestamp(meeting.scheduled_time / 1000, tz=datetime.timezone.utc).astimezone(
            datetime.timezone(datetime.timedelta(hours=5, minutes=30)) # IST
        ).strftime("%I:%M %p, %d %b %Y IST")

        vc_link = meeting.location_details or "Discord Voice Channel"
        if meeting.meet_code:
            vc_link = f"https://cal.gobitsnbytes.org/m/{meeting.meet_code}"

        if email_type == "invite":
            subject = f"📅 Invitation: {meeting.title}"
            ics_content = generate_ics(
                meeting.id, 
                meeting.title, 
                meeting.scheduled_time, 
                meeting.end_time or (meeting.scheduled_time + 1800000), 
                meeting.description, 
                vc_link,
                settings.smtp_from or "gobitsnbytes@gmail.com",
                to_emails
            )
            html = get_invite_html(meeting.title, formatted_time, vc_link, meeting.description)
            send_smtp_email(settings, to_emails, subject, html, ics_content, "invite.ics")

        elif email_type == "cancel":
            subject = f"❌ Cancelled: {meeting.title}"
            html = get_cancel_html(meeting.title, formatted_time)
            send_smtp_email(settings, to_emails, subject, html)

        elif email_type == "reschedule":
            subject = f"🔄 Rescheduled: {meeting.title}"
            
            # Retrieve the previous scheduled time from reschedule history database
            old_time_str = "Previous scheduled time"
            history_stmt = (
                select(MeetingRescheduleHistory)
                .where(MeetingRescheduleHistory.meeting_id == meeting_id)
                .order_by(MeetingRescheduleHistory.created_at.desc())
                .limit(1)
            )
            res_history = await db.execute(history_stmt)
            history_entry = res_history.scalar_one_or_none()
            if history_entry:
                old_time_str = datetime.datetime.fromtimestamp(
                    history_entry.old_scheduled_time / 1000, 
                    tz=datetime.timezone.utc
                ).astimezone(
                    datetime.timezone(datetime.timedelta(hours=5, minutes=30)) # IST
                ).strftime("%I:%M %p, %d %b %Y IST")

            html = get_reschedule_html(
                meeting.title,
                old_time_str,
                formatted_time,
                reschedule_reason or "Time update",
                rescheduled_by or "HQ Organizer",
                vc_link
            )
            ics_content = generate_ics(
                meeting.id, 
                meeting.title, 
                meeting.scheduled_time, 
                meeting.end_time or (meeting.scheduled_time + 1800000), 
                meeting.description, 
                vc_link,
                settings.smtp_from or "gobitsnbytes@gmail.com",
                to_emails
            )
            send_smtp_email(settings, to_emails, subject, html, ics_content, "invite.ics")

# ---------------------------------------------------------------------------
# API Route Handlers
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[MeetingOut])
async def list_meetings(
    db: DbSession,
    status_filter: Optional[str] = None,
    creator_id: Optional[str] = None,
    calcom_booking_id: Optional[str] = None,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Retrieve all meetings matching filters."""
    await require_permission(db, current_user, "meetings.read")
    
    query = select(BotMeeting)
    if status_filter:
        query = query.where(BotMeeting.status == status_filter)
    if creator_id:
        query = query.where(BotMeeting.creator_id == creator_id)
    if calcom_booking_id:
        query = query.where(
            (BotMeeting.calcom_booking_id == calcom_booking_id) |
            (BotMeeting.calcom_uid == calcom_booking_id)
        )
    query = query.order_by(BotMeeting.scheduled_time.desc())

    res = await db.execute(query)
    meetings = res.scalars().all()

    if not meetings:
        return []

    meeting_ids = [m.id for m in meetings]

    # Bulk load attendees
    att_stmt = select(MeetingAttendee).where(MeetingAttendee.meeting_id.in_(meeting_ids))
    res_att = await db.execute(att_stmt)
    all_attendees = res_att.scalars().all()
    attendees_by_meet = {}
    for a in all_attendees:
        attendees_by_meet.setdefault(a.meeting_id, []).append(a)

    # Bulk load transcripts
    tr_stmt = select(MeetingTranscript).where(MeetingTranscript.meeting_id.in_(meeting_ids))
    res_tr = await db.execute(tr_stmt)
    all_transcripts = res_tr.scalars().all()
    transcript_by_meet = {t.meeting_id: t for t in all_transcripts}

    # Bulk load reschedule histories
    rh_stmt = select(MeetingRescheduleHistory).where(MeetingRescheduleHistory.meeting_id.in_(meeting_ids))
    res_rh = await db.execute(rh_stmt)
    all_resched = res_rh.scalars().all()
    resched_by_meet = {}
    for rh in all_resched:
        resched_by_meet.setdefault(rh.meeting_id, []).append(rh)

    meetings_out = []
    for m in meetings:
        attendees = attendees_by_meet.get(m.id, [])
        transcript = transcript_by_meet.get(m.id, None)
        resched_hist = resched_by_meet.get(m.id, [])

        m_dict = {c.name: getattr(m, c.name) for c in m.__table__.columns}
        m_dict["attendees"] = [
            {"meeting_id": a.meeting_id, "attendee_type": a.attendee_type, "discord_id": a.discord_id}
            for a in attendees
        ]
        m_dict["transcript"] = (
            {c.name: getattr(transcript, c.name) for c in transcript.__table__.columns}
            if transcript
            else None
        )
        m_dict["reschedule_history"] = [
            {c.name: getattr(rh, c.name) for c in rh.__table__.columns}
            for rh in resched_hist
        ]
        meetings_out.append(MeetingOut.model_validate(m_dict))

    return meetings_out


@router.post("/schedule", response_model=MeetingOut)
async def schedule_meeting(
    body: MeetingCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Schedule a new internal meeting, record details, and notify guests via email/ICS."""
    await require_permission(db, current_user, "meetings.write")

    meeting_id = f"meet_{int(time.time())}_{uuid.uuid4().hex[:7]}"
    meet_code = f"m_{uuid.uuid4().hex[:8]}" if body.location_type == "discord_vc" else None
    end_time = body.scheduled_time + (body.duration_minutes * 60000)

    new_meet = BotMeeting(
        id=meeting_id,
        title=body.title,
        description=body.description,
        scheduled_time=body.scheduled_time,
        location_type=body.location_type,
        location_details=body.location_details,
        temp_channel_id=None,
        status="scheduled",
        creator_id=body.creator_id,
        created_at=int(time.time() * 1000),
        end_time=end_time,
        external_emails=",".join(body.external_emails) if body.external_emails else None,
        recording_status="none",
        meet_code=meet_code,
        booked_by="motherboard",
        scope=body.scope,
        calcom_booking_id=body.calcom_booking_id,
        calcom_uid=body.calcom_uid,
    )
    db.add(new_meet)

    attendees_added = []
    # Add creator as attendee
    creator_att = MeetingAttendee(meeting_id=meeting_id, attendee_type="user", discord_id=body.creator_id)
    db.add(creator_att)
    attendees_added.append(creator_att)

    # Add other invitees
    for inv in body.invitees:
        att = MeetingAttendee(meeting_id=meeting_id, attendee_type=inv.type, discord_id=inv.id)
        db.add(att)
        attendees_added.append(att)

    await db.commit()
    await db.refresh(new_meet)

    # Queue background task to send invitations
    from app.database import get_sessionmaker
    session_factory = get_sessionmaker()
    background_tasks.add_task(send_meeting_emails_task, meeting_id, "invite", settings, session_factory)

    # Build output dictionary
    m_dict = {c.name: getattr(new_meet, c.name) for c in new_meet.__table__.columns}
    m_dict["attendees"] = [
        {"meeting_id": a.meeting_id, "attendee_type": a.attendee_type, "discord_id": a.discord_id}
        for a in attendees_added
    ]
    m_dict["transcript"] = None
    m_dict["reschedule_history"] = []

    return MeetingOut.model_validate(m_dict)


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting(
    meeting_id: str,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Retrieve detailed metadata of a specific meeting."""
    await require_permission(db, current_user, "meetings.read")

    m_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res_m = await db.execute(m_stmt)
    m = res_m.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")

    att_stmt = select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
    res_att = await db.execute(att_stmt)
    attendees = res_att.scalars().all()

    tr_stmt = select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    res_tr = await db.execute(tr_stmt)
    transcript = res_tr.scalar_one_or_none()

    rh_stmt = select(MeetingRescheduleHistory).where(MeetingRescheduleHistory.meeting_id == meeting_id)
    res_rh = await db.execute(rh_stmt)
    resched_hist = res_rh.scalars().all()

    m_dict = {c.name: getattr(m, c.name) for c in m.__table__.columns}
    m_dict["attendees"] = [
        {"meeting_id": a.meeting_id, "attendee_type": a.attendee_type, "discord_id": a.discord_id}
        for a in attendees
    ]
    m_dict["transcript"] = (
        {c.name: getattr(transcript, c.name) for c in transcript.__table__.columns}
        if transcript
        else None
    )
    m_dict["reschedule_history"] = [
        {c.name: getattr(rh, c.name) for c in rh.__table__.columns}
        for rh in resched_hist
    ]

    return MeetingOut.model_validate(m_dict)


@router.patch("/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    meeting_id: str,
    body: MeetingUpdate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Update meeting parameters. Records reschedule events and notifies invitees on changes."""
    await require_permission(db, current_user, "meetings.write")

    m_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res_m = await db.execute(m_stmt)
    meeting = res_m.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    old_scheduled = meeting.scheduled_time
    old_end = meeting.end_time

    # Apply changes
    update_data = body.model_dump(exclude_unset=True)
    
    # Extract rescheduling variables if applicable
    reschedule_reason = update_data.pop("reschedule_reason", None)
    rescheduled_by = update_data.pop("rescheduled_by", None)

    for key, value in update_data.items():
        if key == "external_emails" and value is not None:
            setattr(meeting, key, ",".join(value))
        else:
            setattr(meeting, key, value)

    # Handle reschedule history log
    if body.scheduled_time and body.scheduled_time != old_scheduled:
        resched = MeetingRescheduleHistory(
            meeting_id=meeting_id,
            old_scheduled_time=old_scheduled,
            old_end_time=old_end,
            new_scheduled_time=body.scheduled_time,
            new_end_time=meeting.end_time,
            reason=reschedule_reason or "Time rescheduled on dashboard",
            rescheduled_by=rescheduled_by or str(current_user.user.display_name),
            rescheduled_at=int(time.time() * 1000)
        )
        db.add(resched)

        # Trigger reschedule emails
        from app.database import get_sessionmaker
        session_factory = get_sessionmaker()
        background_tasks.add_task(
            send_meeting_emails_task,
            meeting_id,
            "reschedule",
            settings,
            session_factory,
            reschedule_reason,
            rescheduled_by or str(current_user.user.display_name)
        )

    await db.commit()
    await db.refresh(meeting)

    # Re-fetch attendees and transcripts
    att_stmt = select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
    res_att = await db.execute(att_stmt)
    attendees = res_att.scalars().all()

    tr_stmt = select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    res_tr = await db.execute(tr_stmt)
    transcript = res_tr.scalar_one_or_none()

    rh_stmt = select(MeetingRescheduleHistory).where(MeetingRescheduleHistory.meeting_id == meeting_id)
    res_rh = await db.execute(rh_stmt)
    resched_hist = res_rh.scalars().all()

    m_dict = {c.name: getattr(meeting, c.name) for c in meeting.__table__.columns}
    m_dict["attendees"] = [
        {"meeting_id": a.meeting_id, "attendee_type": a.attendee_type, "discord_id": a.discord_id}
        for a in attendees
    ]
    m_dict["transcript"] = (
        {c.name: getattr(transcript, c.name) for c in transcript.__table__.columns}
        if transcript
        else None
    )
    m_dict["reschedule_history"] = [
        {c.name: getattr(rh, c.name) for c in rh.__table__.columns}
        for rh in resched_hist
    ]

    return MeetingOut.model_validate(m_dict)


@router.delete("/{meeting_id}", status_code=200)
async def delete_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Cancel a meeting and notify guests."""
    await require_permission(db, current_user, "meetings.write")

    m_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res_m = await db.execute(m_stmt)
    meeting = res_m.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.status = "cancelled"
    
    await db.commit()

    # Trigger cancellation emails in background
    from app.database import get_sessionmaker
    session_factory = get_sessionmaker()
    background_tasks.add_task(send_meeting_emails_task, meeting_id, "cancel", settings, session_factory)

    return {"status": "cancelled"}


@router.post("/{meeting_id}/start", response_model=MeetingOut)
async def start_meeting(
    meeting_id: str,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Activate meeting status."""
    await require_permission(db, current_user, "meetings.write")

    m_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res_m = await db.execute(m_stmt)
    meeting = res_m.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.status = "active"
    meeting.activated_at = int(time.time() * 1000)

    await db.commit()
    await db.refresh(meeting)

    # Re-fetch dependencies
    att_stmt = select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
    res_att = await db.execute(att_stmt)
    attendees = res_att.scalars().all()

    tr_stmt = select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    res_tr = await db.execute(tr_stmt)
    transcript = res_tr.scalar_one_or_none()

    m_dict = {c.name: getattr(meeting, c.name) for c in meeting.__table__.columns}
    m_dict["attendees"] = [
        {"meeting_id": a.meeting_id, "attendee_type": a.attendee_type, "discord_id": a.discord_id}
        for a in attendees
    ]
    m_dict["transcript"] = (
        {c.name: getattr(transcript, c.name) for c in transcript.__table__.columns}
        if transcript
        else None
    )
    m_dict["reschedule_history"] = []

    return MeetingOut.model_validate(m_dict)


@router.post("/{meeting_id}/stop", response_model=MeetingOut)
async def stop_meeting(
    meeting_id: str,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Mark meeting status as completed."""
    await require_permission(db, current_user, "meetings.write")

    m_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res_m = await db.execute(m_stmt)
    meeting = res_m.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.status = "completed"

    await db.commit()
    await db.refresh(meeting)

    att_stmt = select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
    res_att = await db.execute(att_stmt)
    attendees = res_att.scalars().all()

    tr_stmt = select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    res_tr = await db.execute(tr_stmt)
    transcript = res_tr.scalar_one_or_none()

    m_dict = {c.name: getattr(meeting, c.name) for c in meeting.__table__.columns}
    m_dict["attendees"] = [
        {"meeting_id": a.meeting_id, "attendee_type": a.attendee_type, "discord_id": a.discord_id}
        for a in attendees
    ]
    m_dict["transcript"] = (
        {c.name: getattr(transcript, c.name) for c in transcript.__table__.columns}
        if transcript
        else None
    )
    m_dict["reschedule_history"] = []

    return MeetingOut.model_validate(m_dict)


# ---------------------------------------------------------------------------
# Speak timeline calculation and transcription pipeline
# ---------------------------------------------------------------------------

def format_ms_to_timestamp(ms: int) -> str:
    total_seconds = int(ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def build_speaker_turn_slots(timeline: List[SpeakingTimelineItem], session_start_time: int) -> List[dict]:
    """Interleaves speaking timeline slots, resolving overlaps via first-in-wins logic."""
    if not timeline:
        return []

    # 1. Filter out sub-500ms noise bursts and resolve relative times
    events = []
    for e in timeline:
        duration = e.endTime - e.startTime
        if duration >= 500:
            events.append({
                "displayName": e.displayName or "Unknown Speaker",
                "userId": e.userId,
                "startMs": max(0, e.startTime - session_start_time),
                "endMs": max(0, e.endTime - session_start_time)
            })
    
    events = [ev for ev in events if ev["endMs"] > ev["startMs"]]
    if not events:
        return []

    # 2. Sort events by startMs
    events.sort(key=lambda x: x["startMs"])

    # 3. Sweep-line slot interleaving
    slots = []
    cursor = 0
    for evt in events:
        start = max(evt["startMs"], cursor)
        end = evt["endMs"]
        if end <= start:
            continue
        
        last = slots[-1] if slots else None
        if last and last["displayName"] == evt["displayName"] and (start - last["endMs"]) <= 800:
            # Merge small gap
            last["endMs"] = max(last["endMs"], end)
        else:
            slots.append({
                "displayName": evt["displayName"],
                "startMs": start,
                "endMs": end
            })
        cursor = max(cursor, end)

    return slots


@router.post("/{meeting_id}/transcribe", response_model=MeetingTranscriptSchema)
async def transcribe_meeting(
    meeting_id: str,
    db: DbSession,
    file: UploadFile = File(...),
    metadata: str = Form(...),
    current_user: ResolvedPrincipal = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Multipart upload receiver that runs the Gemini AI transcription pipeline."""
    await require_permission(db, current_user, "meetings.write")

    # 1. Verify meeting exists
    m_stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res_m = await db.execute(m_stmt)
    meeting = res_m.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 2. Parse metadata
    try:
        meta_dict = json.loads(metadata)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse metadata JSON: {e}")

    duration_seconds = meta_dict.get("durationSeconds", 0)
    speakers = meta_dict.get("speakers", [])
    vc_text_messages = meta_dict.get("vcTextMessages", [])
    start_time = meta_dict.get("startTime", 0)
    raw_timeline = meta_dict.get("speakingTimeline", [])

    timeline_items = []
    for item in raw_timeline:
        try:
            timeline_items.append(SpeakingTimelineItem.model_validate(item))
        except Exception:
            pass

    # 3. Calculate Speaker Turn slots
    slots = build_speaker_turn_slots(timeline_items, start_time)
    
    slots_lines = []
    for idx, s in enumerate(slots):
        start_str = format_ms_to_timestamp(s["startMs"])
        end_str = format_ms_to_timestamp(s["endMs"])
        slots_lines.append(f"{idx+1}. [{start_str}–{end_str}] → {s['displayName']}")
    slots_text = "\n".join(slots_lines)

    speaker_names = ", ".join([sp.get("displayName", "Unknown") for sp in speakers]) or "Unknown"
    duration_min = round(duration_seconds / 60)
    max_words = int(duration_min * 150 * (len(speakers) or 1))

    speaker_slots_section = ""
    if slots_text:
        speaker_slots_section = f"""
## Deterministic Speaker Turn Table
The following table was computed from Discord's voice activity events and is **ground truth**.
Each row is a non-overlapping time window and the speaker assigned to it.
You MUST attribute every utterance to the speaker whose slot covers that timestamp.
Do NOT infer speakers from voice characteristics — use ONLY this table.

{slots_text}

If speech occurs outside all listed slots, label it as "Unknown Speaker".
If a slot contains only silence, background noise, or is inaudible, write [silence] or [inaudible] — do NOT fabricate speech."""

    # 4. Build prompt
    prompt = f"""You are a professional meeting transcriber and note-taker for the Bits&Bytes team.

## Meeting Information
- **Title**: {meeting.title}
- **Duration**: {duration_min} minutes ({duration_seconds} seconds)
- **Known Participants**: {speaker_names}{speaker_slots_section}

## Your Task
Transcribe the audio recording of this meeting. The participants may speak in:
- **English**
- **Hindi** (हिन्दी)
- **Hinglish** (a natural mix of Hindi and English, very common in Indian workplaces)

## MANDATORY ANTI-HALLUCINATION RULES — FOLLOW THESE EXACTLY:
1. **Do NOT fabricate or guess words.** If speech is unclear or inaudible, write [inaudible] at that point. Never substitute with plausible-sounding words.
2. **Do NOT add content beyond what is actually spoken.** The recording is {duration_min} minutes long. Your transcript must not imply significantly more speech than could occur in {duration_min} minutes (~{max_words} words maximum across all speakers).
3. **Do NOT transcribe background noise, music, microphone rustling, or the consent announcement audio** played at the start of the recording. Skip those and begin from actual meeting speech.
4. **Do NOT invent participants, decisions, or action items** that were not explicitly mentioned.
5. **Silence and gaps are normal** — do not fill them with fabricated dialogue.

## Speaker Attribution Rules:
6. **Use the "Deterministic Speaker Turn Table" above as the ONLY source for who is speaking at any timestamp.** Do not try to distinguish voices acoustically.
7. **Do NOT translate.** If someone says "yaar ye feature toh bahut important hai", write it exactly as spoken in Hinglish — do NOT convert to English.
8. **Timestamps**: Provide timestamps in [MM:SS] format relative to the start of the recording.
9. **Summary and action items**: Write these in English for consistency, even if the meeting was in Hindi/Hinglish.

## Required Output Format
Respond with ONLY a valid JSON object (no markdown code blocks, no extra text) with these exact fields:

{{
  "summary": "A clear 3-5 sentence summary of the meeting in English",
  "keyDecisions": ["Decision 1", "Decision 2"],
  "actionItems": [
    {{"assignee": "Person Name", "task": "What they need to do", "deadline": "By when (if mentioned)"}}
  ],
  "fullTranscript": "Speaker-labeled transcript with paragraphs. Use the speaker's name followed by a colon. Use [inaudible] for unclear speech.",
  "timestampedTranscript": "[00:00] Speaker: What they said\\n[00:15] Another Speaker: Their response\\n..."
}}

If no decisions or action items were discussed, use empty arrays [].
If you cannot determine a deadline for an action item, omit the deadline field."""

    # 5. Save audio locally to a temporary file
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"{meeting_id}_upload.ogg")
    with open(temp_file_path, "wb") as f:
        f.write(await file.read())

    # 6. Call Gemini API via google-genai
    if not settings.gemini_api_key:
        # Cleanup file
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY settings are missing on Motherboard")

    try:
        from google import genai
        from google.genai import types

        logger.info("[TRANSCRIBER] Uploading file to Google GenAI File API...")
        client = genai.Client(api_key=settings.gemini_api_key)
        uploaded_file = client.files.upload(file=temp_file_path, config={"mime_type": "audio/ogg"})
        logger.info("[TRANSCRIBER] File uploaded to Gemini: %s", uploaded_file.uri)

        # Generate transcript content with fallback support
        try:
            logger.info("[TRANSCRIBER] Generating content with model %s...", settings.gemini_model)
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
        except Exception as primary_err:
            fallback_model = "gemini-2.5-flash"
            if settings.gemini_model != fallback_model:
                logger.warning(
                    "[TRANSCRIBER] Primary model %s failed: %s. Falling back to %s...",
                    settings.gemini_model,
                    primary_err,
                    fallback_model
                )
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=[uploaded_file, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
            else:
                raise primary_err

        text_out = response.text
        if not text_out:
            raise ValueError("Empty response received from Gemini.")

        # Cleanup Google File
        try:
            client.files.delete(name=uploaded_file.name)
            logger.info("[TRANSCRIBER] Cleaned up Google File API record.")
        except Exception as cleanup_err:
            logger.warning("[TRANSCRIBER] Failed to delete file on Google File API: %s", cleanup_err)

    except Exception as gemini_err:
        logger.error("[TRANSCRIBER] Gemini API exception: %s", gemini_err)
        # Cleanup local file
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Gemini API failure: {gemini_err}")

    # Cleanup local file
    try:
        os.unlink(temp_file_path)
    except Exception:
        pass

    # 7. Parse output
    text_out = text_out.strip()
    if text_out.startswith("```json"):
        text_out = text_out[7:]
    if text_out.startswith("```"):
        text_out = text_out[3:]
    if text_out.endswith("```"):
        text_out = text_out[:-3]
    text_out = text_out.strip()

    try:
        data = json.loads(text_out)
    except Exception:
        logger.warning("[TRANSCRIBER] JSON parse failed, falling back to plaintext")
        data = {
            "summary": "Transcript generated but structure parse failed.",
            "keyDecisions": [],
            "actionItems": [],
            "fullTranscript": text_out,
            "timestampedTranscript": ""
        }

    # 8. Save transcript in database
    # Check if transcript already exists
    stmt_ex = select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    res_ex = await db.execute(stmt_ex)
    existing_transcript = res_ex.scalar_one_or_none()

    if existing_transcript:
        await db.execute(
            update(MeetingTranscript)
            .where(MeetingTranscript.meeting_id == meeting_id)
            .values(
                summary=data.get("summary"),
                key_decisions=json.dumps(data.get("keyDecisions", [])),
                action_items=json.dumps(data.get("actionItems", [])),
                full_transcript=data.get("fullTranscript"),
                timestamped_transcript=data.get("timestampedTranscript"),
                vc_text_messages=json.dumps(vc_text_messages),
                audio_duration_seconds=duration_seconds,
                speaker_count=len(speakers),
                processed_at=datetime.datetime.utcnow().isoformat() + "Z"
            )
        )
    else:
        new_tr = MeetingTranscript(
            meeting_id=meeting_id,
            summary=data.get("summary"),
            key_decisions=json.dumps(data.get("keyDecisions", [])),
            action_items=json.dumps(data.get("actionItems", [])),
            full_transcript=data.get("fullTranscript"),
            timestamped_transcript=data.get("timestampedTranscript"),
            vc_text_messages=json.dumps(vc_text_messages),
            audio_duration_seconds=duration_seconds,
            speaker_count=len(speakers),
            processed_at=datetime.datetime.utcnow().isoformat() + "Z"
        )
        db.add(new_tr)

    # Resolve speaker accounts and add them to attendees list
    for sp in speakers:
        sp_id = sp.get("userId")
        if sp_id:
            # Check if attendee already in database
            stmt_att = select(MeetingAttendee).where(
                (MeetingAttendee.meeting_id == meeting_id) & (MeetingAttendee.discord_id == sp_id)
            )
            res_att = await db.execute(stmt_att)
            if not res_att.scalar_one_or_none():
                db.add(MeetingAttendee(meeting_id=meeting_id, attendee_type="user", discord_id=sp_id))

    # 9. Resolve assignees and create ActionItems in DB
    action_items_parsed = data.get("actionItems", [])
    if isinstance(action_items_parsed, list):
        for item in action_items_parsed:
            assignee_name = item.get("assignee", "").strip()
            task_text = item.get("task", "").strip()
            deadline = item.get("deadline", "")
            
            if not task_text:
                continue

            resolved_discord_id = None
            # Match assignee name with displayNames in speakers list
            if assignee_name:
                for sp in speakers:
                    if sp.get("displayName", "").lower().strip() == assignee_name.lower():
                        resolved_discord_id = sp.get("userId")
                        break

            # Create action item record
            new_ai = ActionItem(
                meeting_id=meeting_id,
                assignee=assignee_name,
                discord_id=resolved_discord_id,
                task=task_text,
                deadline=deadline,
                status="pending",
                created_at=int(time.time() * 1000)
            )
            db.add(new_ai)

    # Set recording status to completed
    meeting.recording_status = "completed"
    await db.commit()

    # Build response schema
    out_dict = {
        "meeting_id": meeting_id,
        "summary": data.get("summary"),
        "key_decisions": json.dumps(data.get("keyDecisions", [])),
        "action_items": json.dumps(data.get("actionItems", [])),
        "full_transcript": data.get("fullTranscript"),
        "timestamped_transcript": data.get("timestampedTranscript"),
        "vc_text_messages": json.dumps(vc_text_messages),
        "audio_duration_seconds": duration_seconds,
        "speaker_count": len(speakers),
        "processed_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    return MeetingTranscriptSchema.model_validate(out_dict)


# ---------------------------------------------------------------------------
# Public Endpoints (no auth required – used by Chrono booking portal)
# ---------------------------------------------------------------------------

@router.get("/public/hosts", response_model=List[UserAvailabilitySchema])
async def list_public_hosts(db: DbSession):
    """Return all users who have a booking link set. Public – no auth needed.
    Used by the Chrono booking portal (cal.gobitsnbytes.org) to render host cards.
    """
    stmt = select(UserAvailability).where(UserAvailability.booking_link.isnot(None))
    res = await db.execute(stmt)
    hosts = res.scalars().all()
    return [UserAvailabilitySchema.model_validate(h) for h in hosts]


@router.get("/public/availability/{booking_link}", response_model=UserAvailabilitySchema)
async def get_public_availability_by_link(booking_link: str, db: DbSession):
    """Return a user's public availability profile by their booking link slug.
    Public – no auth needed. Used by the Chrono booking flow.
    """
    stmt = select(UserAvailability).where(UserAvailability.booking_link == booking_link)
    res = await db.execute(stmt)
    avail = res.scalar_one_or_none()
    if not avail:
        raise HTTPException(status_code=404, detail="Booking link not found")
    return UserAvailabilitySchema.model_validate(avail)


@router.get("/public/availability/{booking_link}/slots", response_model=List[str])
async def get_availability_slots(
    booking_link: str,
    date: str,
    db: DbSession,
    duration: int = 30
):
    """Calculate free slots for a host by booking link slug. Public endpoint."""
    stmt = select(UserAvailability).where(UserAvailability.booking_link == booking_link)
    res = await db.execute(stmt)
    host = res.scalar_one_or_none()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    import zoneinfo
    try:
        tz = zoneinfo.ZoneInfo(host.timezone or "Asia/Kolkata")
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")

    try:
        target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    local_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=tz)
    local_end = datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=tz)

    start_utc_ms = int(local_start.timestamp() * 1000)
    end_utc_ms = int(local_end.timestamp() * 1000)
    now_ms = int(time.time() * 1000)

    # Fetch scheduled meetings for the host (as creator or attendee)
    meeting_stmt = (
        select(BotMeeting)
        .outerjoin(MeetingAttendee, BotMeeting.id == MeetingAttendee.meeting_id)
        .where(
            (BotMeeting.status != "cancelled") &
            ((BotMeeting.creator_id == host.discord_id) | (MeetingAttendee.discord_id == host.discord_id))
        )
    )
    res_meetings = await db.execute(meeting_stmt)
    meetings = res_meetings.scalars().all()

    # Deduplicate meetings list
    meetings_dict = {m.id: m for m in meetings}
    meetings = list(meetings_dict.values())

    try:
        weekly_hours = json.loads(host.weekly_hours or "{}")
    except Exception:
        weekly_hours = {}

    utc_slots = []

    for day_offset in [-1, 0, 1]:
        d = target_date + datetime.timedelta(days=day_offset)
        day_of_week_name = d.strftime("%A").lower()
        daily_slots = weekly_hours.get(day_of_week_name, [])

        for slot_range in daily_slots:
            start_str = slot_range.get("start", "")
            end_str = slot_range.get("end", "")
            if not start_str or not end_str:
                continue

            try:
                start_h, start_m = map(int, start_str.split(":"))
                end_h, end_m = map(int, end_str.split(":"))
            except ValueError:
                continue

            current_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m

            while current_min + duration <= end_min:
                h = current_min // 60
                m = current_min % 60

                slot_time = datetime.time(h, m)
                slot_local_dt = datetime.datetime.combine(d, slot_time).replace(tzinfo=tz)

                slot_start_ms = int(slot_local_dt.timestamp() * 1000)
                slot_end_ms = slot_start_ms + duration * 60 * 1000

                if start_utc_ms <= slot_start_ms <= end_utc_ms and slot_start_ms > now_ms:
                    overlaps = False
                    for m in meetings:
                        m_start = m.scheduled_time
                        m_end = m.end_time if m.end_time else (m_start + 30 * 60 * 1000)

                        if slot_start_ms < m_end and slot_end_ms > m_start:
                            overlaps = True
                            break

                    if not overlaps:
                        utc_slot_dt = datetime.datetime.fromtimestamp(slot_start_ms / 1000, tz=datetime.timezone.utc)
                        utc_slots.append(utc_slot_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

                current_min += 15

    utc_slots.sort()
    return utc_slots


from pydantic import BaseModel
import random
import hmac
import hashlib

# Transient storage for OTP codes: email -> {"code": str, "expires_at": float}
guest_otp_store: dict[str, dict[str, Any]] = {}

# Transient storage for verified guest tokens: token -> {"email": str, "expires_at": float}
verified_guest_tokens: dict[str, dict[str, Any]] = {}

class GuestVerificationSendRequest(BaseModel):
    email: str

class GuestVerificationVerifyRequest(BaseModel):
    email: str
    code: str

class GuestCancelRequest(BaseModel):
    email: str
    token: str
    reason: Optional[str] = None

class GuestRescheduleRequest(BaseModel):
    email: str
    token: str
    new_slot_iso: str
    duration_minutes: int = 30
    reason: Optional[str] = None

def check_guest_token(token: Optional[str], email: str) -> bool:
    if not token:
        return False
    entry = verified_guest_tokens.get(token)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        verified_guest_tokens.pop(token, None)
        return False
    return entry["email"] == email.strip().lower()

@router.post("/public/guest/verification/send")
async def send_guest_otp(body: GuestVerificationSendRequest, settings: Settings = Depends(get_settings)):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Invalid email format")
    
    # Generate 6-digit OTP
    otp = f"{random.randint(100000, 999999)}"
    guest_otp_store[email] = {
        "code": otp,
        "expires_at": time.time() + 600 # 10 mins
    }
    
    # Format email body
    html_body = get_base_email_html(f"""
    <div class="card">
        <h2 class="card-title">VERIFY YOUR EMAIL</h2>
        <p style="font-size: 14px; line-height: 1.6; color: #f7f1ec;">
            You requested a verification code to manage your bookings on bits&bytes™. Use the 6-digit OTP code below:
        </p>
        <div style="background-color: rgba(255, 122, 27, 0.1); border: 2px dashed #ff7a1b; border-radius: 12px; padding: 20px; text-align: center; margin: 25px 0;">
            <span style="font-size: 32px; font-weight: 800; letter-spacing: 5px; color: #ff7a1b; font-family: monospace;">{otp}</span>
        </div>
        <p style="font-size: 11px; color: rgba(247, 241, 236, 0.4); line-height: 1.4; margin-top: 15px;">
            This verification code is transient and will expire in 10 minutes. If you did not initiate this request, you can safely ignore this email.
        </p>
    </div>
    """, "Verify Email")

    # Send the email via SMTP helper
    send_smtp_email(
        settings=settings,
        to_emails=[email],
        subject=f"bits&bytes™ Verification Code: {otp}",
        html_body=html_body
    )
    
    return {"status": "sent", "email": email}


@router.post("/public/guest/verification/verify")
async def verify_guest_otp(body: GuestVerificationVerifyRequest, settings: Settings = Depends(get_settings)):
    email = body.email.strip().lower()
    code = body.code.strip()
    
    entry = guest_otp_store.get(email)
    if not entry:
        raise HTTPException(status_code=400, detail="No verification code sent or it has expired. Please request a new code.")
        
    if time.time() > entry["expires_at"]:
        guest_otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")
        
    if entry["code"] != code:
        raise HTTPException(status_code=400, detail="Invalid verification code. Please try again.")
        
    # Generate secure token
    token = hmac.new(
        settings.api_internal_secret.encode(),
        f"{email}:{time.time()}:{random.random()}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Store token valid for 1 hour
    verified_guest_tokens[token] = {
        "email": email,
        "expires_at": time.time() + 3600
    }
    
    # Clean up OTP
    guest_otp_store.pop(email, None)
    
    return {"status": "verified", "token": token}


@router.get("/public/guest/mine")
async def get_guest_meetings(email: str, token: str, db: DbSession):
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Invalid email format")
    if not check_guest_token(token, email):
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")
    
    stmt = select(BotMeeting).where(
        (BotMeeting.status == "scheduled") | (BotMeeting.status == "active"),
        BotMeeting.external_emails.ilike(f"%{email}%")
    ).limit(20)
    
    res = await db.execute(stmt)
    meetings = res.scalars().all()
    
    return [
        {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "scheduled_time": m.scheduled_time,
            "end_time": m.end_time,
            "meet_code": m.meet_code
        }
        for m in meetings
    ]


@router.post("/public/guest/{meeting_id}/cancel")
async def cancel_guest_meeting(meeting_id: str, body: GuestCancelRequest, db: DbSession):
    if not check_guest_token(body.token, body.email):
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")

    stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res = await db.execute(stmt)
    meeting = res.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    if meeting.status not in ["scheduled", "active"]:
        raise HTTPException(status_code=400, detail="Meeting cannot be cancelled from its current state")
        
    if not meeting.external_emails or body.email.lower() not in meeting.external_emails.lower():
        raise HTTPException(status_code=403, detail="Unauthorized: email not found in guest list")
        
    meeting.status = "cancelled"
    await db.commit()
    
    return {"status": "cancelled", "meeting_id": meeting_id}


@router.post("/public/guest/{meeting_id}/reschedule")
async def reschedule_guest_meeting(meeting_id: str, body: GuestRescheduleRequest, db: DbSession):
    if not check_guest_token(body.token, body.email):
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")

    stmt = select(BotMeeting).where(BotMeeting.id == meeting_id)
    res = await db.execute(stmt)
    meeting = res.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    if meeting.status not in ["scheduled", "active"]:
        raise HTTPException(status_code=400, detail="Meeting cannot be rescheduled from its current state")
        
    if not meeting.external_emails or body.email.lower() not in meeting.external_emails.lower():
        raise HTTPException(status_code=403, detail="Unauthorized: email not found in guest list")
        
    try:
        new_slot_dt = datetime.datetime.fromisoformat(body.new_slot_iso.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid new_slot_iso format. Expected ISO 8601 string.")
        
    new_scheduled_ms = int(new_slot_dt.timestamp() * 1000)
    new_end_ms = new_scheduled_ms + body.duration_minutes * 60 * 1000
    now_ms = int(time.time() * 1000)
    
    history_entry = MeetingRescheduleHistory(
        meeting_id=meeting.id,
        old_scheduled_time=meeting.scheduled_time,
        old_end_time=meeting.end_time,
        new_scheduled_time=new_scheduled_ms,
        new_end_time=new_end_ms,
        reason=body.reason or "Guest requested reschedule",
        rescheduled_by=body.email,
        rescheduled_at=now_ms
    )
    
    db.add(history_entry)
    meeting.scheduled_time = new_scheduled_ms
    meeting.end_time = new_end_ms
    
    await db.commit()
    
    return {
        "status": "rescheduled",
        "meeting_id": meeting_id,
        "new_scheduled_time": new_scheduled_ms,
        "new_end_time": new_end_ms
    }


# ---------------------------------------------------------------------------
# Availability Endpoint
# ---------------------------------------------------------------------------

@router.get("/availability/{discord_id}", response_model=UserAvailabilitySchema)
async def get_user_availability(
    discord_id: str,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Get availability configuration of a user."""
    await require_permission(db, current_user, "meetings.read")

    stmt = select(UserAvailability).where(UserAvailability.discord_id == discord_id)
    res = await db.execute(stmt)
    avail = res.scalar_one_or_none()
    if not avail:
        raise HTTPException(status_code=404, detail="Availability profile not found")

    return UserAvailabilitySchema.model_validate(avail)


@router.post("/availability", response_model=UserAvailabilitySchema)
async def upsert_user_availability(
    body: UserAvailabilitySchema,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Upsert availability configuration."""
    await require_permission(db, current_user, "meetings.write")

    stmt = select(UserAvailability).where(UserAvailability.discord_id == body.discord_id)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        for c in UserAvailability.__table__.columns:
            if c.name != "discord_id":
                setattr(existing, c.name, getattr(body, c.name))
        avail = existing
    else:
        avail = UserAvailability(
            discord_id=body.discord_id,
            username=body.username,
            email=body.email,
            timezone=body.timezone,
            weekly_hours=body.weekly_hours,
            booking_link=body.booking_link,
            title=body.title,
            description=body.description,
            calcom_event_type_id=body.calcom_event_type_id,
            associated_role_id=body.associated_role_id,
            avatar=body.avatar
        )
        db.add(avail)

    await db.commit()
    await db.refresh(avail)
    return UserAvailabilitySchema.model_validate(avail)


# ---------------------------------------------------------------------------
# Email Preferences Endpoints
# ---------------------------------------------------------------------------

@router.get("/preferences/{discord_id}", response_model=MeetingEmailPreferenceSchema)
async def get_email_preferences(
    discord_id: str,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Get email preferences for a user."""
    await require_permission(db, current_user, "meetings.read")

    stmt = select(MeetingEmailPreference).where(MeetingEmailPreference.discord_id == discord_id)
    res = await db.execute(stmt)
    pref = res.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Email preferences profile not found")

    return MeetingEmailPreferenceSchema.model_validate(pref)


@router.post("/preferences", response_model=MeetingEmailPreferenceSchema)
async def upsert_email_preferences(
    body: MeetingEmailPreferenceSchema,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Upsert email preferences for a user."""
    await require_permission(db, current_user, "meetings.write")

    stmt = select(MeetingEmailPreference).where(MeetingEmailPreference.discord_id == body.discord_id)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.email = body.email
        existing.notify_on_invite = body.notify_on_invite
        existing.notify_on_reminder = body.notify_on_reminder
        existing.updated_at = int(time.time() * 1000)
        pref = existing
    else:
        pref = MeetingEmailPreference(
            discord_id=body.discord_id,
            email=body.email,
            notify_on_invite=body.notify_on_invite,
            notify_on_reminder=body.notify_on_reminder,
            updated_at=int(time.time() * 1000)
        )
        db.add(pref)

    await db.commit()
    await db.refresh(pref)
    return MeetingEmailPreferenceSchema.model_validate(pref)


# ---------------------------------------------------------------------------
# Action Items Endpoints
# ---------------------------------------------------------------------------

@router.get("/{meeting_id}/action-items", response_model=List[ActionItemSchema])
async def list_meeting_action_items(
    meeting_id: str,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """List action items for a specific meeting."""
    await require_permission(db, current_user, "meetings.read")
    
    stmt = select(ActionItem).where(ActionItem.meeting_id == meeting_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{meeting_id}/action-items", response_model=ActionItemSchema)
async def create_action_item(
    meeting_id: str,
    body: ActionItemCreate,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Add a new custom action item."""
    await require_permission(db, current_user, "meetings.write")

    ai = ActionItem(
        meeting_id=meeting_id,
        assignee=body.assignee,
        discord_id=body.discord_id,
        task=body.task,
        deadline=body.deadline,
        status="pending",
        created_at=int(time.time() * 1000)
    )
    db.add(ai)
    await db.commit()
    await db.refresh(ai)
    return ai


@router.patch("/action-items/{action_item_id}/status", response_model=ActionItemSchema)
async def update_action_item_status(
    action_item_id: int,
    body: ActionItemStatusUpdate,
    db: DbSession,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Update action item status (e.g. mark completed)."""
    await require_permission(db, current_user, "meetings.write")

    stmt = select(ActionItem).where(ActionItem.id == action_item_id)
    res = await db.execute(stmt)
    ai = res.scalar_one_or_none()
    if not ai:
        raise HTTPException(status_code=404, detail="Action item not found")

    ai.status = body.status
    await db.commit()
    await db.refresh(ai)
    return ai

# Trigger rebuild for sudoers fix
