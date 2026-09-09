"""Add idempotency_key to signature_requests table

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-08-02 13:16:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'signature_requests',
        sa.Column('idempotency_key', sa.String(length=100), nullable=True)
    )
    op.create_index(
        op.f('ix_signature_requests_idempotency_key'),
        'signature_requests',
        ['idempotency_key'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_signature_requests_idempotency_key'), table_name='signature_requests')
    op.drop_column('signature_requests', 'idempotency_key')
