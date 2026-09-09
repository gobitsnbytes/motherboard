"""Add OTP verification fields to signature_recipients table

Revision ID: d4e5f6a1b2c3
Revises: g1h2i3j4k5l6
Create Date: 2026-08-05 11:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'signature_recipients',
        sa.Column('requires_otp', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column(
        'signature_recipients',
        sa.Column('otp_code', sa.String(length=6), nullable=True)
    )
    op.add_column(
        'signature_recipients',
        sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('signature_recipients', 'otp_expires_at')
    op.drop_column('signature_recipients', 'otp_code')
    op.drop_column('signature_recipients', 'requires_otp')
