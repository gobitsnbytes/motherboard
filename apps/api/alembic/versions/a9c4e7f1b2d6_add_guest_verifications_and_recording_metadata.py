"""add guest_verifications table and meetings.recording_metadata

Revision ID: a9c4e7f1b2d6
Revises: h1i2j3k4l5m6
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c4e7f1b2d6'
down_revision: Union[str, None] = 'h1i2j3k4l5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('guest_verifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('otp_hash', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('booking_link', sa.String(length=255), nullable=True),
        sa.Column('meeting_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guest_verifications_email'), 'guest_verifications', ['email'], unique=False)
    op.create_index(op.f('ix_guest_verifications_expires_at'), 'guest_verifications', ['expires_at'], unique=False)
    op.add_column(
        'meetings',
        sa.Column('recording_metadata', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('meetings', 'recording_metadata')
    op.drop_index(op.f('ix_guest_verifications_expires_at'), table_name='guest_verifications')
    op.drop_index(op.f('ix_guest_verifications_email'), table_name='guest_verifications')
    op.drop_table('guest_verifications')
