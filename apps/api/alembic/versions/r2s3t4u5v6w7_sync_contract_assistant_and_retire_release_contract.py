"""Sync contract assistant tables and retire the unused release-contract schema.

Revision ID: r2s3t4u5v6w7
Revises: q0r1s2t3u4v5

The Contract Assistant models and signature_recipients.allowed_sig_type shipped
without migrations, and the release-contract tables added in p9q0r1s2t3u4 were
superseded by the semantic OOXML review flow and dropped from the models. Both
gaps failed `alembic check`.
"""

from alembic import op
import sqlalchemy as sa


revision = "r2s3t4u5v6w7"
down_revision = "q0r1s2t3u4v5"
branch_labels = None
depends_on = None


RETIRED_INDEXES = (
    ("ix_onboarding_evidence_document_id", "onboarding_evidence"),
    ("ix_onboarding_evidence_revision_id", "onboarding_evidence"),
    ("ix_onboarding_guardian_checks_case_id", "onboarding_guardian_checks"),
    ("ix_onboarding_guardian_checks_revision_id", "onboarding_guardian_checks"),
    ("ix_onboarding_guardian_checks_participant_id", "onboarding_guardian_checks"),
    ("ix_onboarding_authorities_document_key", "onboarding_authorities"),
    ("ix_onboarding_template_versions_document_key", "onboarding_template_versions"),
)


def upgrade() -> None:
    op.create_table(
        "ca_contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("counterparty", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="in_review"),
        sa.Column("value", sa.String(length=100), nullable=True),
        sa.Column("original_file_path", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ca_contracts_message_id", "ca_contracts", ["message_id"], unique=True)

    op.create_table(
        "ca_clauses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.String(length=50), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["contract_id"], ["ca_contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ca_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("clause_id", sa.Uuid(), nullable=True),
        sa.Column("clause_ref", sa.String(length=50), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("risk_type", sa.String(length=100), nullable=False),
        sa.Column("plain_english", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("policy_link", sa.Text(), nullable=True),
        sa.Column("template_fix", sa.Text(), nullable=True),
        sa.Column("suggested_rewrite", sa.Text(), nullable=True),
        sa.Column("tier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
        sa.Column("dismissed_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["clause_id"], ["ca_clauses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["ca_contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ca_signatories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="signer"),
        sa.Column("envelope_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(["contract_id"], ["ca_contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ca_envelopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("signature_request_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["contract_id"], ["ca_contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signature_request_id"], ["signature_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ca_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contract_id"], ["ca_contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("signature_recipients", sa.Column("allowed_sig_type", sa.String(length=50), nullable=True))
    op.execute("UPDATE signature_recipients SET allowed_sig_type = 'any' WHERE allowed_sig_type IS NULL")

    # One unique index replaces the redundant unique constraint plus plain index.
    op.drop_constraint("onboarding_participants_portal_token_hash_key", "onboarding_participants", type_="unique")
    op.drop_index("ix_onboarding_participants_portal_token_hash", table_name="onboarding_participants")
    op.create_index("ix_onboarding_participants_portal_token_hash", "onboarding_participants", ["portal_token_hash"], unique=True)

    # The revision pointers survive as plain columns; only the release-contract
    # foreign keys go, because their target tables are being retired.
    op.drop_constraint("fk_onboarding_cases_current_revision", "onboarding_cases", type_="foreignkey")
    op.drop_constraint("fk_onboarding_documents_revision", "onboarding_documents", type_="foreignkey")
    op.drop_constraint("fk_onboarding_participants_revision", "onboarding_participants", type_="foreignkey")
    op.drop_constraint("fk_onboarding_reviews_revision", "onboarding_reviews", type_="foreignkey")
    op.drop_index("ix_onboarding_reviews_revision_id", table_name="onboarding_reviews")
    op.drop_column("onboarding_reviews", "revision_id")

    for index, table in RETIRED_INDEXES:
        op.drop_index(index, table_name=table)
    op.drop_table("onboarding_evidence")
    op.drop_table("onboarding_guardian_checks")
    op.drop_table("onboarding_authorities")
    op.drop_table("onboarding_template_versions")


def downgrade() -> None:
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
    for index, table in RETIRED_INDEXES:
        op.create_index(index, table, [index.replace(f"ix_{table}_", "")])

    op.add_column("onboarding_reviews", sa.Column("revision_id", sa.Uuid(), nullable=True))
    op.create_index("ix_onboarding_reviews_revision_id", "onboarding_reviews", ["revision_id"])
    op.create_foreign_key("fk_onboarding_reviews_revision", "onboarding_reviews", "onboarding_revisions", ["revision_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_onboarding_participants_revision", "onboarding_participants", "onboarding_revisions", ["revision_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_onboarding_documents_revision", "onboarding_documents", "onboarding_revisions", ["revision_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_onboarding_cases_current_revision", "onboarding_cases", "onboarding_revisions", ["current_revision_id"], ["id"], ondelete="SET NULL")

    op.drop_index("ix_onboarding_participants_portal_token_hash", table_name="onboarding_participants")
    op.create_index("ix_onboarding_participants_portal_token_hash", "onboarding_participants", ["portal_token_hash"])
    op.create_unique_constraint("onboarding_participants_portal_token_hash_key", "onboarding_participants", ["portal_token_hash"])

    op.drop_column("signature_recipients", "allowed_sig_type")
    op.drop_table("ca_events")
    op.drop_table("ca_envelopes")
    op.drop_table("ca_signatories")
    op.drop_table("ca_findings")
    op.drop_table("ca_clauses")
    op.drop_index("ix_ca_contracts_message_id", table_name="ca_contracts")
    op.drop_table("ca_contracts")
