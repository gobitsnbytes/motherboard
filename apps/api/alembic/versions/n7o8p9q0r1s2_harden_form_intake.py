"""Harden public form file intake against duplicate upload retries.

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
"""

from alembic import op
import sqlalchemy as sa


revision = "n7o8p9q0r1s2"
down_revision = "m6n7o8p9q0r1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "public_form_submissions",
        sa.Column("intake_status", sa.String(length=20), server_default="complete", nullable=False),
    )
    op.add_column(
        "public_form_submissions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "public_form_uploads",
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_form_upload_content",
        "public_form_uploads",
        ["submission_id", "field_id", "content_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_form_upload_content", "public_form_uploads", type_="unique")
    op.drop_column("public_form_uploads", "content_fingerprint")
    op.drop_column("public_form_submissions", "completed_at")
    op.drop_column("public_form_submissions", "intake_status")
