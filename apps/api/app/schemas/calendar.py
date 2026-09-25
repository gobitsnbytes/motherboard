from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConnectionCreate(StrictModel):
    user_id: UUID | None = None
    shared_host_name: str | None = Field(default=None, min_length=2, max_length=100)
    shared_host_email: EmailStr | None = None
    api_key: str = Field(min_length=8, max_length=500)

    @model_validator(mode="after")
    def require_one_host(self):
        if (self.user_id is None) == (self.shared_host_name is None):
            raise ValueError("Choose an existing host or name a shared host")
        if (self.shared_host_name is None) != (self.shared_host_email is None):
            raise ValueError("Shared hosts require both a name and email")
        return self


class ConnectionOut(StrictModel):
    id: UUID
    user_id: UUID
    provider: str
    cal_user_id: str | None
    cal_username: str | None
    status: str
    last_verified_at: datetime | None
    last_error_code: str | None

    model_config = ConfigDict(from_attributes=True)


class RoutingPoolCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    algorithm: Literal["round_robin", "weighted_round_robin", "priority"] = "round_robin"


class RoutingPoolPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    algorithm: Literal["round_robin", "weighted_round_robin", "priority"] | None = None
    active: bool | None = None


class RoutingPoolOut(StrictModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    algorithm: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class PublicPoolOut(StrictModel):
    name: str
    description: str | None
    ready: bool


class PoolMemberCreate(StrictModel):
    calendar_connection_id: UUID
    event_type_id: int = Field(gt=0)
    weight: int = Field(default=1, ge=1, le=100)
    priority: int = Field(default=100, ge=0, le=10000)
    daily_booking_limit: int | None = Field(default=None, ge=1, le=1000)


class PoolMemberOut(StrictModel):
    id: UUID
    pool_id: UUID
    calendar_connection_id: UUID
    event_type_id: int
    event_type_slug: str | None
    weight: int
    priority: int
    daily_booking_limit: int | None
    active: bool
    last_assigned_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PublicBookingCreate(StrictModel):
    start: datetime
    attendee_name: str = Field(min_length=1, max_length=120)
    attendee_email: EmailStr
    attendee_timezone: str = Field(min_length=1, max_length=100)
    guest_emails: list[EmailStr] = Field(default_factory=list, max_length=10)

    @field_validator("start")
    @classmethod
    def start_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start must include a timezone")
        return value


class BookingMutation(StrictModel):
    reason: str | None = Field(default=None, max_length=500)


class BookingReschedule(BookingMutation):
    start: datetime

    @field_validator("start")
    @classmethod
    def start_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start must include a timezone")
        return value


class BookingOut(StrictModel):
    uid: str
    status: str
    start: datetime
    end: datetime
    meeting_url: str | None = None
    host_user_id: UUID
    management_token: str


class AdminBookingOut(StrictModel):
    uid: str
    status: str
    start: datetime
    end: datetime
    meeting_url: str | None = None
    host_user_id: UUID
    attendee_name: str
    attendee_email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class SlotOut(StrictModel):
    start: datetime
    end: datetime


class WebhookAck(StrictModel):
    status: Literal["processed", "duplicate"]


def public_provider_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Keep private Cal.com payload details out of public responses."""
    return {key: data.get(key) for key in ("uid", "status", "start", "end")}
