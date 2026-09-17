"""Add revisioned onboarding release contract.

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
    op.create_table(
        "onboarding_template_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_key", sa.String(length=60), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("template_filename", sa.String(length=255), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("field_schema", sa.JSON(), nullable=False),
        sa.Column("signature_anchors", sa.JSON(), nullable=False),
        sa.Column("renderer_version", sa.String(length=120), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key", "version", name="uq_onboarding_template_version"),
    )
    op.create_index("ix_onboarding_template_versions_document_key", "onboarding_template_versions", ["document_key"])

    op.create_table(
        "onboarding_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="collecting"),
        sa.Column("answer_snapshot", sa.JSON(), nullable=False),
        sa.Column("template_snapshot", sa.JSON(), nullable=False),
        sa.Column("notice_snapshot", sa.JSON(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("supersession_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["case_id"], ["onboarding_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["onboarding_revisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "number", name="uq_onboarding_revision_number"),
    )
    op.create_index("ix_onboarding_revisions_case_id", "onboarding_revisions", ["case_id"])
    op.add_column("onboarding_cases", sa.Column("current_revision_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_onboarding_cases_current_revision", "onboarding_cases", "onboarding_revisions", ["current_revision_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_onboarding_cases_current_revision_id", "onboarding_cases", ["current_revision_id"])

    op.add_column("onboarding_participants", sa.Column("revision_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_onboarding_participants_revision", "onboarding_participants", "onboarding_revisions", ["revision_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_onboarding_participants_revision_id", "onboarding_participants", ["revision_id"])
    op.add_column("onboarding_documents", sa.Column("revision_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_onboarding_documents_revision", "onboarding_documents", "onboarding_revisions", ["revision_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_onboarding_documents_revision_id", "onboarding_documents", ["revision_id"])
    op.add_column("onboarding_reviews", sa.Column("revision_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_onboarding_reviews_revision", "onboarding_reviews", "onboarding_revisions", ["revision_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_onboarding_reviews_revision_id", "onboarding_reviews", ["revision_id"])

    op.create_table(
        "onboarding_guardian_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["case_id"], ["onboarding_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["onboarding_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["onboarding_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (("case_id", "case_id"), ("revision_id", "revision_id"), ("participant_id", "participant_id")):
        op.create_index(f"ix_onboarding_guardian_checks_{name}", "onboarding_guardian_checks", [column])

    op.create_table(
        "onboarding_authorities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_key", sa.String(length=60), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("signer_name", sa.String(length=255), nullable=False),
        sa.Column("signer_email", sa.String(length=255), nullable=False),
        sa.Column("authority_reference", sa.String(length=255), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_authorities_document_key", "onboarding_authorities", ["document_key"])

    op.create_table(
        "onboarding_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_type", sa.String(length=60), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["onboarding_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["onboarding_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "document_id", "artifact_type", name="uq_onboarding_evidence_artifact"),
    )
    op.create_index("ix_onboarding_evidence_revision_id", "onboarding_evidence", ["revision_id"])
    op.create_index("ix_onboarding_evidence_document_id", "onboarding_evidence", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_evidence_document_id", table_name="onboarding_evidence")
    op.drop_index("ix_onboarding_evidence_revision_id", table_name="onboarding_evidence")
    op.drop_table("onboarding_evidence")
    op.drop_index("ix_onboarding_authorities_document_key", table_name="onboarding_authorities")
    op.drop_table("onboarding_authorities")
    for name in ("participant_id", "revision_id", "case_id"):
        op.drop_index(f"ix_onboarding_guardian_checks_{name}", table_name="onboarding_guardian_checks")
    op.drop_table("onboarding_guardian_checks")
    op.drop_index("ix_onboarding_reviews_revision_id", table_name="onboarding_reviews")
    op.drop_constraint("fk_onboarding_reviews_revision", "onboarding_reviews", type_="foreignkey")
    op.drop_column("onboarding_reviews", "revision_id")
    op.drop_index("ix_onboarding_documents_revision_id", table_name="onboarding_documents")
    op.drop_constraint("fk_onboarding_documents_revision", "onboarding_documents", type_="foreignkey")
    op.drop_column("onboarding_documents", "revision_id")
    op.drop_index("ix_onboarding_participants_revision_id", table_name="onboarding_participants")
    op.drop_constraint("fk_onboarding_participants_revision", "onboarding_participants", type_="foreignkey")
    op.drop_column("onboarding_participants", "revision_id")
    op.drop_index("ix_onboarding_cases_current_revision_id", table_name="onboarding_cases")
    op.drop_constraint("fk_onboarding_cases_current_revision", "onboarding_cases", type_="foreignkey")
    op.drop_column("onboarding_cases", "current_revision_id")
    op.drop_index("ix_onboarding_revisions_case_id", table_name="onboarding_revisions")
    op.drop_table("onboarding_revisions")
    op.drop_index("ix_onboarding_template_versions_document_key", table_name="onboarding_template_versions")
    op.drop_table("onboarding_template_versions")
