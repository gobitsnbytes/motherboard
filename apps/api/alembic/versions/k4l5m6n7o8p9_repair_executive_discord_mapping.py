"""Repair the canonical Executive Leadership Discord mapping.

The seeded role was observed mapped to Super Admin in production. Only the
known role id is changed, and only when its current target is Super Admin.
"""

from alembic import op
import sqlalchemy as sa


revision = "k4l5m6n7o8p9"
down_revision = "j3k4l5m6n7o8"
branch_labels = None
depends_on = None


EXECUTIVE_ROLE_ID = "1506019032015310949"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE discord_role_mappings
            SET group_id = (
                SELECT id FROM groups WHERE slug = 'sg_executive'
            ),
                updated_at = CURRENT_TIMESTAMP
            WHERE discord_role_id = :role_id
              AND group_id = (
                  SELECT id FROM groups WHERE slug = 'sg_super_admin'
              )
            """
        ).bindparams(role_id=EXECUTIVE_ROLE_ID)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE discord_role_mappings
            SET group_id = (
                SELECT id FROM groups WHERE slug = 'sg_super_admin'
            ),
                updated_at = CURRENT_TIMESTAMP
            WHERE discord_role_id = :role_id
              AND group_id = (
                  SELECT id FROM groups WHERE slug = 'sg_executive'
              )
            """
        ).bindparams(role_id=EXECUTIVE_ROLE_ID)
    )
