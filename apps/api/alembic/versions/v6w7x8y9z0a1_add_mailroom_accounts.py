"""Add encrypted Mailroom mailbox accounts and sign-in codes.

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mailroom_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_authenticated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "ai_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    # One mailbox per identity. The model declares unique and indexed on the
    # same column, which is a unique index rather than a separate constraint.
    op.create_index(
        "ix_mailroom_accounts_user_id", "mailroom_accounts", ["user_id"], unique=True
    )

    op.create_table(
        "mailroom_otp_challenges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["mailroom_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # One live challenge per mailbox, for the same reason.
    op.create_index(
        "ix_mailroom_otp_challenges_account_id",
        "mailroom_otp_challenges",
        ["account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mailroom_otp_challenges_account_id", table_name="mailroom_otp_challenges"
    )
    op.drop_table("mailroom_otp_challenges")
    op.drop_index("ix_mailroom_accounts_user_id", table_name="mailroom_accounts")
    op.drop_table("mailroom_accounts")
