"""add calcom fields to events table

Revision ID: a1b2c3d4e5f6
Revises: cdd5a04f9914
Create Date: 2026-07-16

Adds calcom_booking_id and calcom_uid columns to the events table.
These fields are needed so event-update.js can cancel Cal.com bookings
when an event is cancelled via /event-update status:Cancelled.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '13ecd7a65443'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add calcom_booking_id column to events table
    op.add_column('events', sa.Column('calcom_booking_id', sa.String(255), nullable=True))
    # Add calcom_uid column to events table
    op.add_column('events', sa.Column('calcom_uid', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('events', 'calcom_uid')
    op.drop_column('events', 'calcom_booking_id')
