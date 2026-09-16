"""Add Cal.com routing tables.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "m6n7o8p9q0r1"
down_revision = "l5m6n7o8p9q0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "calendar_connections",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), server_default="calcom", nullable=False),
        sa.Column("cal_user_id", sa.String(100)),
        sa.Column("cal_username", sa.String(100)),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("webhook_secret", sa.Text()),
        sa.Column("provider_webhook_id", sa.String(100)),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_calendar_connection_user_provider"),
    )
    op.create_index("ix_calendar_connections_user_id", "calendar_connections", ["user_id"])

    op.create_table(
        "routing_pools",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("algorithm", sa.String(30), server_default="round_robin", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_routing_pools_slug", "routing_pools", ["slug"], unique=True)

    op.create_table(
        "routing_pool_members",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("pool_id", uuid, sa.ForeignKey("routing_pools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("calendar_connection_id", uuid, sa.ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type_id", sa.Integer(), nullable=False),
        sa.Column("event_type_slug", sa.String(120)),
        sa.Column("weight", sa.Integer(), server_default="1", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("daily_booking_limit", sa.Integer()),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_assigned_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pool_id", "calendar_connection_id", "event_type_id", name="uq_routing_pool_member_event_type"),
    )
    op.create_index("ix_routing_pool_members_pool_id", "routing_pool_members", ["pool_id"])
    op.create_index("ix_routing_pool_members_calendar_connection_id", "routing_pool_members", ["calendar_connection_id"])
    op.create_index("ix_routing_pool_members_last_assigned_at", "routing_pool_members", ["last_assigned_at"])

    op.create_table(
        "calendar_bookings",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("provider", sa.String(30), server_default="calcom", nullable=False),
        sa.Column("provider_booking_uid", sa.String(255), nullable=False),
        sa.Column("provider_booking_id", sa.String(100)),
        sa.Column("routing_pool_id", uuid, sa.ForeignKey("routing_pools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("routing_pool_member_id", uuid, sa.ForeignKey("routing_pool_members.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type_id", sa.Integer(), nullable=False),
        sa.Column("host_user_id", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attendee_name", sa.String(120), nullable=False),
        sa.Column("attendee_email", sa.String(255), nullable=False),
        sa.Column("attendee_timezone", sa.String(100), nullable=False),
        sa.Column("guest_emails", sa.JSON()),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("meeting_url", sa.Text()),
        sa.Column("rescheduled_from_uid", sa.String(255)),
        sa.Column("rescheduled_to_uid", sa.String(255)),
        sa.Column("provider_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_calendar_bookings_provider_booking_uid", "calendar_bookings", ["provider_booking_uid"], unique=True)
    op.create_index("ix_calendar_bookings_routing_pool_id", "calendar_bookings", ["routing_pool_id"])
    op.create_index("ix_calendar_bookings_host_user_id", "calendar_bookings", ["host_user_id"])
    op.create_index("ix_calendar_bookings_attendee_email", "calendar_bookings", ["attendee_email"])
    op.create_index("ix_calendar_bookings_start_at", "calendar_bookings", ["start_at"])

    op.create_table(
        "calendar_webhook_events",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("connection_id", uuid, sa.ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("trigger", sa.String(80), nullable=False),
        sa.Column("booking_uid", sa.String(255)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="received", nullable=False),
        sa.Column("error_details", sa.String(500)),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_calendar_webhook_events_connection_id", "calendar_webhook_events", ["connection_id"])
    op.create_index("ix_calendar_webhook_events_event_key", "calendar_webhook_events", ["event_key"], unique=True)
    op.create_index("ix_calendar_webhook_events_booking_uid", "calendar_webhook_events", ["booking_uid"])

    op.create_table(
        "routing_decisions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("routing_pool_id", uuid, sa.ForeignKey("routing_pools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_duration_minutes", sa.Integer()),
        sa.Column("candidate_snapshot", sa.JSON()),
        sa.Column("selected_member_id", uuid, sa.ForeignKey("routing_pool_members.id", ondelete="SET NULL")),
        sa.Column("outcome", sa.String(30), server_default="pending", nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("provider_booking_uid", sa.String(255)),
        sa.Column("response_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_routing_decisions_idempotency_key", "routing_decisions", ["idempotency_key"], unique=True)
    op.create_index("ix_routing_decisions_routing_pool_id", "routing_decisions", ["routing_pool_id"])


def downgrade() -> None:
    op.drop_table("routing_decisions")
    op.drop_table("calendar_webhook_events")
    op.drop_table("calendar_bookings")
    op.drop_table("routing_pool_members")
    op.drop_table("routing_pools")
    op.drop_table("calendar_connections")
