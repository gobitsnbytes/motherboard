"""Store recipient-bound OTP hashes and bounded verification state.

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u4
"""

from alembic import op
import sqlalchemy as sa


revision = "q0r1s2t3u4v5"
down_revision = "p9q0r1s2t3u4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signature_recipients", sa.Column("otp_hash", sa.String(length=64), nullable=True))
    op.add_column("signature_recipients", sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("signature_recipients", sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=True))
    # Existing plaintext codes are invalidated rather than copied. Recipients
    # request a new code generated under the hash-only contract.
    op.execute("UPDATE signature_recipients SET otp_code = NULL")


def downgrade() -> None:
    op.drop_column("signature_recipients", "otp_verified_at")
    op.drop_column("signature_recipients", "otp_attempts")
    op.drop_column("signature_recipients", "otp_hash")
