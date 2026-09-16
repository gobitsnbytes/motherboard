"""Retain historical duplicate form entries but hide them from operations.

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
"""

from alembic import op
import sqlalchemy as sa


revision = "o8p9q0r1s2t3"
down_revision = "n7o8p9q0r1s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "public_form_submissions",
        sa.Column("duplicate_of_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_form_submission_duplicate_of",
        "public_form_submissions",
        "public_form_submissions",
        ["duplicate_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_public_form_submissions_duplicate_of_id",
        "public_form_submissions",
        ["duplicate_of_id"],
    )
    # jsonb has deterministic structural equality. The earliest exact response
    # remains canonical; later exact matches remain in the database for audit.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                first_value(id) OVER (
                    PARTITION BY form_id, answers::jsonb
                    ORDER BY created_at ASC, id ASC
                ) AS canonical_id,
                row_number() OVER (
                    PARTITION BY form_id, answers::jsonb
                    ORDER BY created_at ASC, id ASC
                ) AS position
            FROM public_form_submissions
        )
        UPDATE public_form_submissions AS submission
        SET duplicate_of_id = ranked.canonical_id
        FROM ranked
        WHERE submission.id = ranked.id
          AND ranked.position > 1
        """
    )


def downgrade() -> None:
    op.drop_index("ix_public_form_submissions_duplicate_of_id", table_name="public_form_submissions")
    op.drop_constraint("fk_form_submission_duplicate_of", "public_form_submissions", type_="foreignkey")
    op.drop_column("public_form_submissions", "duplicate_of_id")
