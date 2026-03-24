"""Align role permissions with separated role experiences

Revision ID: 20260324_01
Revises: 20260108_01
Create Date: 2026-03-24
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260324_01"
down_revision = "20260108_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (
          SELECT id FROM roles WHERE code IN ('superadmin', 'leader', 'collaborator', 'admin')
        );
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (
          (r.code = 'superadmin' AND p.code IN (
            'training.view',
            'training.complete',
            'training.quiz',
            'checklist.view',
            'roles.manage',
            'users.manage',
            'training.manage',
            'training.assign',
            'training.monitor'
          ))
          OR
          (r.code = 'leader' AND p.code IN (
            'training.view',
            'checklist.view',
            'training.monitor'
          ))
          OR
          (r.code = 'collaborator' AND p.code IN (
            'training.view',
            'training.complete',
            'training.quiz'
          ))
          OR
          (r.code = 'admin' AND p.code IN (
            'training.view',
            'checklist.view',
            'training.manage',
            'training.assign'
          ))
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (
          SELECT id FROM roles WHERE code IN ('superadmin', 'leader', 'collaborator', 'admin')
        );
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON (
          (r.code = 'superadmin' AND p.code IN (
            'training.view',
            'training.complete',
            'training.quiz',
            'checklist.view',
            'roles.manage',
            'users.manage',
            'training.manage',
            'training.assign',
            'training.monitor'
          ))
          OR
          (r.code = 'leader' AND p.code IN (
            'training.view',
            'checklist.view',
            'training.monitor'
          ))
          OR
          (r.code = 'collaborator' AND p.code IN (
            'training.view',
            'training.complete',
            'training.quiz'
          ))
          OR
          (r.code = 'admin' AND p.code IN (
            'training.view',
            'training.complete',
            'training.quiz',
            'checklist.view'
          ))
        );
        """
    )
