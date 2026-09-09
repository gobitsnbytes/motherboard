"""Add public form builder tables.

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "i2j3k4l5m6n7"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

def upgrade() -> None:
    op.create_table("public_forms", sa.Column("id", UUID, primary_key=True), sa.Column("title", sa.String(160), nullable=False), sa.Column("slug", sa.String(160), nullable=False), sa.Column("description_markdown", sa.Text()), sa.Column("blocks", sa.JSON(), nullable=False), sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_public_forms_slug", "public_forms", ["slug"], unique=True)
    op.create_table("public_form_submissions", sa.Column("id", UUID, primary_key=True), sa.Column("form_id", UUID, sa.ForeignKey("public_forms.id", ondelete="CASCADE"), nullable=False), sa.Column("answers", sa.JSON(), nullable=False), sa.Column("idempotency_key", sa.String(100), nullable=False), sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ip_address", sa.String(50)), sa.Column("user_agent", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("form_id", "idempotency_key", name="uq_form_submission_idempotency"))
    op.create_index("ix_public_form_submissions_form_id", "public_form_submissions", ["form_id"])
    op.create_table("public_form_uploads", sa.Column("id", UUID, primary_key=True), sa.Column("submission_id", UUID, sa.ForeignKey("public_form_submissions.id", ondelete="CASCADE"), nullable=False), sa.Column("field_id", sa.String(100), nullable=False), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("content_type", sa.String(100)), sa.Column("storage_path", sa.Text(), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_public_form_uploads_submission_id", "public_form_uploads", ["submission_id"])
    op.create_index("ix_public_form_uploads_expires_at", "public_form_uploads", ["expires_at"])

def downgrade() -> None:
    op.drop_table("public_form_uploads")
    op.drop_table("public_form_submissions")
    op.drop_table("public_forms")
