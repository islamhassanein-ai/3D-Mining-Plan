"""add_trench_sample_fields

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-07-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trench', sa.Column('sample_id', sa.String(), nullable=True))
    op.add_column('trench', sa.Column('from_depth', sa.Float(), nullable=True))
    op.add_column('trench', sa.Column('to_depth', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('trench', 'to_depth')
    op.drop_column('trench', 'from_depth')
    op.drop_column('trench', 'sample_id')
