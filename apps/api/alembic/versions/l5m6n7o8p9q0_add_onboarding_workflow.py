"""add digital onboarding workflow tables"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_cases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="collecting"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("reviewer_id", sa.UUID(), nullable=True),
        sa.Column("fork_id", sa.UUID(), nullable=True),
        sa.Column("case_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fork_id"], ["forks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_cases_fork_id", "onboarding_cases", ["fork_id"])

    op.create_table(
        "onboarding_participants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("date_of_birth", sa.String(length=10), nullable=True),
        sa.Column("is_minor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="invited"),
        sa.Column("portal_token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["onboarding_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_token_hash"),
    )
    op.create_index("ix_onboarding_participants_case_id", "onboarding_participants", ["case_id"])
    op.create_index("ix_onboarding_participants_portal_token_hash", "onboarding_participants", ["portal_token_hash"])

    op.create_table(
        "onboarding_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("participant_id", sa.UUID(), nullable=True),
        sa.Column("document_key", sa.String(length=60), nullable=False),
        sa.Column("template_filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="awaiting_completion"),
        sa.Column("source_docx_path", sa.Text(), nullable=True),
        sa.Column("filled_docx_path", sa.Text(), nullable=True),
        sa.Column("source_pdf_path", sa.Text(), nullable=True),
        sa.Column("signature_request_id", sa.UUID(), nullable=True),
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
        sa.Column("canonical_hash", sa.String(length=64), nullable=True),
        sa.Column("field_values", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["onboarding_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["onboarding_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signature_request_id"], ["signature_requests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "participant_id", "document_key", name="uq_onboarding_document_key"),
    )
    op.create_index("ix_onboarding_documents_case_id", "onboarding_documents", ["case_id"])

    op.create_table(
        "onboarding_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["onboarding_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["onboarding_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_reviews_case_id", "onboarding_reviews", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_reviews_case_id", table_name="onboarding_reviews")
    op.drop_table("onboarding_reviews")
    op.drop_index("ix_onboarding_documents_case_id", table_name="onboarding_documents")
    op.drop_table("onboarding_documents")
    op.drop_index("ix_onboarding_participants_portal_token_hash", table_name="onboarding_participants")
    op.drop_index("ix_onboarding_participants_case_id", table_name="onboarding_participants")
    op.drop_table("onboarding_participants")
    op.drop_index("ix_onboarding_cases_fork_id", table_name="onboarding_cases")
    op.drop_table("onboarding_cases")
