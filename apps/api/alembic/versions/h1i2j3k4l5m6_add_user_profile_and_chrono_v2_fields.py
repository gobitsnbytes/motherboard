"""Add user profile and chrono_v2 fields to users table

Revision ID: h1i2j3k4l5m6
Revises: e5f6a1b2c3d4
Create Date: 2026-08-05 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, None] = 'a7f3c92b1d84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('title', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('timezone', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('skills', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('chrono_v2_data', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('profile_completed', sa.Boolean(), server_default=sa.text('false'), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'profile_completed')
    op.drop_column('users', 'chrono_v2_data')
    op.drop_column('users', 'skills')
    op.drop_column('users', 'timezone')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'title')
