"""Pydantic v2 schemas for Meeting and Transcription endpoints."""

import uuid
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Any

class MeetingAttendeeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    attendee_type: str
    discord_id: str


class MeetingCreateAttendee(BaseModel):
    type: str # 'user' or 'role'
    id: str


class MeetingCreate(BaseModel):
    title: str
    description: str | None = None
    scheduled_time: int  # Epoch timestamp in milliseconds
    duration_minutes: int = 30
    location_type: str  # 'discord_vc' or 'external'
    location_details: str | None = None
    creator_id: str
    invitees: list[MeetingCreateAttendee] = []
    external_emails: list[str] = []
    notes: str | None = None
    scope: str = "invite"


class MeetingRescheduleHistorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: str
    old_scheduled_time: int
    old_end_time: int | None
    new_scheduled_time: int
    new_end_time: int | None
    reason: str
    rescheduled_by: str
    rescheduled_at: int


class MeetingTranscriptSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    summary: str | None = None
    key_decisions: str | None = None
    action_items: str | None = None
    full_transcript: str | None = None
    timestamped_transcript: str | None = None
    vc_text_messages: str | None = None
    audio_duration_seconds: int | None = None
    speaker_count: int | None = None
    processed_at: str | None = None


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    scheduled_time: int
    location_type: str
    location_details: str | None
    temp_channel_id: str | None
    status: str
    creator_id: str
    created_at: int
    calcom_booking_id: str | None
    calcom_uid: str | None
    end_time: int | None
    external_emails: str | None
    recording_status: str
    meet_code: str | None
    booked_by: str | None
    scope: str
    activated_at: int | None

    attendees: list[MeetingAttendeeSchema] = []
    transcript: MeetingTranscriptSchema | None = None
    reschedule_history: list[MeetingRescheduleHistorySchema] = []


class MeetingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    scheduled_time: int | None = None
    duration_minutes: int | None = None
    location_type: str | None = None
    location_details: str | None = None
    temp_channel_id: str | None = None
    status: str | None = None
    external_emails: list[str] | None = None
    recording_status: str | None = None
    meet_code: str | None = None
    scope: str | None = None
    reschedule_reason: str | None = None
    rescheduled_by: str | None = None


class UserAvailabilitySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    discord_id: str
    username: str
    email: EmailStr | None = None
    timezone: str = "Asia/Kolkata"
    weekly_hours: str | None = None
    booking_link: str | None = None
    title: str | None = None
    description: str | None = None
    calcom_event_type_id: str | None = None
    associated_role_id: str | None = None
    avatar: str | None = None


class UserAvailabilityUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    timezone: str | None = None
    weekly_hours: str | None = None
    booking_link: str | None = None
    title: str | None = None
    description: str | None = None
    calcom_event_type_id: str | None = None
    associated_role_id: str | None = None
    avatar: str | None = None


class MeetingEmailPreferenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    discord_id: str
    email: str
    notify_on_invite: int = 1
    notify_on_reminder: int = 1
    updated_at: int | None = None


class MeetingEmailPreferenceUpdate(BaseModel):
    email: str
    notify_on_invite: int | None = None
    notify_on_reminder: int | None = None


class ActionItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: str
    assignee: str
    discord_id: str | None
    task: str
    deadline: str | None
    status: str
    notified_at: int | None
    created_at: int


class ActionItemCreate(BaseModel):
    assignee: str
    discord_id: str | None = None
    task: str
    deadline: str | None = None


class ActionItemStatusUpdate(BaseModel):
    status: str


class TimelineSpeaker(BaseModel):
    userId: str
    displayName: str


class VcChatMessage(BaseModel):
    author: str
    content: str
    timestamp: int


class SpeakingTimelineItem(BaseModel):
    userId: str
    displayName: str | None = None
    startTime: int
    endTime: int


class TranscribeMeetingRequest(BaseModel):
    title: str
    scheduledTime: int
    durationSeconds: int
    speakers: list[TimelineSpeaker]
    vcTextMessages: list[VcChatMessage]
    startTime: int
    speakingTimeline: list[SpeakingTimelineItem] = []

