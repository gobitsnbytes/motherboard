"""Add semantic OOXML revisions and PR-style onboarding review threads.

Revision ID: p9q0r1s2t3u4
Revises: o8p9q0r1s2t3
"""

from alembic import op
import sqlalchemy as sa


revision = "p9q0r1s2t3u4"
down_revision = "o8p9q0r1s2t3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onboarding_documents", sa.Column("current_revision", sa.Integer(), server_default="0", nullable=False))
    op.add_column("onboarding_documents", sa.Column("draft_package_path", sa.Text(), nullable=True))
    op.add_column("onboarding_documents", sa.Column("template_hash", sa.String(length=64), nullable=True))
    op.add_column("onboarding_documents", sa.Column("state_hash", sa.String(length=64), nullable=True))
    op.add_column("onboarding_documents", sa.Column("final_docx_hash", sa.String(length=64), nullable=True))
    op.add_column("onboarding_documents", sa.Column("final_pdf_hash", sa.String(length=64), nullable=True))
    op.add_column("onboarding_documents", sa.Column("participant_signed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onboarding_documents", sa.Column("hq_signed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onboarding_documents", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "onboarding_document_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("field_values", sa.JSON(), nullable=False),
        sa.Column("package_path", sa.Text(), nullable=False),
        sa.Column("package_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_state_hash", sa.String(length=64), nullable=True),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_kind", sa.String(length=30), nullable=False),
        sa.Column("actor_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["onboarding_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "revision", name="uq_onboarding_document_revision"),
    )
    op.create_index("ix_onboarding_document_revisions_document_id", "onboarding_document_revisions", ["document_id"])

    op.create_table(
        "onboarding_review_threads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("field_id", sa.String(length=160), nullable=True),
        sa.Column("block_id", sa.String(length=160), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["onboarding_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_review_threads_document_id", "onboarding_review_threads", ["document_id"])

    op.create_table(
        "onboarding_review_comments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=False),
        sa.Column("author_kind", sa.String(length=30), nullable=False),
        sa.Column("author_ref", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["onboarding_review_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_review_comments_thread_id", "onboarding_review_comments", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_review_comments_thread_id", table_name="onboarding_review_comments")
    op.drop_table("onboarding_review_comments")
    op.drop_index("ix_onboarding_review_threads_document_id", table_name="onboarding_review_threads")
    op.drop_table("onboarding_review_threads")
    op.drop_index("ix_onboarding_document_revisions_document_id", table_name="onboarding_document_revisions")
    op.drop_table("onboarding_document_revisions")
    for column in (
        "finalized_at", "hq_signed_at", "participant_signed_at", "final_pdf_hash", "final_docx_hash",
        "state_hash", "template_hash", "draft_package_path", "current_revision",
    ):
        op.drop_column("onboarding_documents", column)
