"""add_collar_hole_type

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-28 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('collar', sa.Column('hole_type', sa.String(10), nullable=True))
    # Backfill existing rows so the new column is never NULL in practice;
    # historical collars created by the four-file import flow are all DD.
    op.execute("UPDATE collar SET hole_type = 'DD' WHERE hole_type IS NULL")
    op.create_index(
        'idx_collar_project_hole_type', 'collar', ['project_id', 'hole_type']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_collar_project_hole_type', table_name='collar')
    op.drop_column('collar', 'hole_type')