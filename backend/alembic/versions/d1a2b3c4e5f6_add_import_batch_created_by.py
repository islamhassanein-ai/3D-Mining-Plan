"""add_import_batch_created_by

Revision ID: d1a2b3c4e5f6
Revises: c49a4e0e8c79
Create Date: 2026-07-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c49a4e0e8c79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('import_batch', sa.Column('created_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_import_batch_created_by_user_account',
        'import_batch', 'user_account',
        ['created_by'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_import_batch_created_by_user_account', 'import_batch', type_='foreignkey')
    op.drop_column('import_batch', 'created_by')
