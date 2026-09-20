"""Allow Department Leads to independently review onboarding cases.

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


PERMISSIONS = ("onboarding.read", "onboarding.review")


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
        WHERE g.slug = 'sg_department_lead'
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
    for permission_key in PERMISSIONS:
        connection.execute(
            statement,
            {"id": uuid.uuid4(), "permission_key": permission_key},
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM grants
            WHERE principal_type = 'group'
              AND principal_id = (
                  SELECT id FROM groups WHERE slug = 'sg_department_lead'
              )
              AND permission_key IN ('onboarding.read', 'onboarding.review')
              AND resource_scope IS NULL
            """
        )
    )
