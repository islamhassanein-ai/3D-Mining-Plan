"""add_project_owner_id

Revision ID: e7f8a9b0c1d2
Revises: bc78a0b106d0
Create Date: 2026-07-18 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'bc78a0b106d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('project', sa.Column('owner_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_project_owner_id_user_account',
        'project', 'user_account',
        ['owner_id'], ['id']
    )
    op.create_index(op.f('ix_project_owner_id'), 'project', ['owner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_project_owner_id'), table_name='project')
    op.drop_constraint('fk_project_owner_id_user_account', 'project', type_='foreignkey')
    op.drop_column('project', 'owner_id')
