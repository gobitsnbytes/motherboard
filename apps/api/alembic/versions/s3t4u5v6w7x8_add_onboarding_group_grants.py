"""Add least-privilege onboarding grants for HQ and Executive Leadership.

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


GROUP_GRANTS = (
    ("sg_hq", "onboarding.read"),
    ("sg_hq", "onboarding.write"),
    ("sg_executive", "onboarding.read"),
    ("sg_executive", "onboarding.review"),
    ("sg_executive", "onboarding.certificate"),
)


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO grants
            (id, principal_type, principal_id, permission_key, resource_scope)
        SELECT
            :id, 'group', g.id, p.key, NULL
        FROM groups g
        JOIN permissions p ON p.key = :permission_key
        WHERE g.slug = :group_slug
          AND NOT EXISTS (
              SELECT 1
              FROM grants existing
              WHERE existing.principal_type = 'group'
                AND existing.principal_id = g.id
                AND existing.permission_key = p.key
                AND existing.resource_scope IS NULL
          )
        """
    )
    for group_slug, permission_key in GROUP_GRANTS:
        connection.execute(
            statement,
            {
                "id": uuid.uuid4(),
                "group_slug": group_slug,
                "permission_key": permission_key,
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        """
        DELETE FROM grants
        WHERE principal_type = 'group'
          AND principal_id = (SELECT id FROM groups WHERE slug = :group_slug)
          AND permission_key = :permission_key
          AND resource_scope IS NULL
        """
    )
    for group_slug, permission_key in GROUP_GRANTS:
        connection.execute(
            statement,
            {"group_slug": group_slug, "permission_key": permission_key},
        )
