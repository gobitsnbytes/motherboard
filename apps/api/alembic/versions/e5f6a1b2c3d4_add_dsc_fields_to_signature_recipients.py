"""Add DSC fields to signature_recipients table

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-08-05 11:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, None] = 'd4e5f6a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'signature_recipients',
        sa.Column('dsc_type', sa.String(length=50), nullable=True)
    )
    op.add_column(
        'signature_recipients',
        sa.Column('dsc_issuer', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'signature_recipients',
        sa.Column('dsc_serial', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'signature_recipients',
        sa.Column('dsc_common_name', sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('signature_recipients', 'dsc_common_name')
    op.drop_column('signature_recipients', 'dsc_serial')
    op.drop_column('signature_recipients', 'dsc_issuer')
    op.drop_column('signature_recipients', 'dsc_type')
