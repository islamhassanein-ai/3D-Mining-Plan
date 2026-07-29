"""add_trench_polyline_fields

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-07-28 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # All columns are nullable: the two legacy trench uploaders in
    # backend/src/api/projects.py never set these fields, and existing rows
    # have no values. point_order arrives with the future Sampling/Assay Sheet.
    op.add_column('trench', sa.Column('point_order', sa.Integer(), nullable=True))
    op.add_column('trench', sa.Column('hole_type', sa.String(10), nullable=True))
    op.add_column(
        'trench',
        sa.Column('import_batch_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_trench_import_batch_id',
        'trench',
        'import_batch',
        ['import_batch_id'],
        ['id'],
    )
    op.add_column(
        'trench',
        sa.Column('superseded_by', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_trench_superseded_by',
        'trench',
        'trench',
        ['superseded_by'],
        ['id'],
    )
    op.add_column('trench', sa.Column('dip', sa.Float(), nullable=True))
    op.add_column('trench', sa.Column('azimuth', sa.Float(), nullable=True))
    op.create_index(
        'idx_trench_project_trench_order',
        'trench',
        ['project_id', 'trench_id', 'point_order'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_trench_project_trench_order', table_name='trench')
    op.drop_column('trench', 'azimuth')
    op.drop_column('trench', 'dip')
    op.drop_constraint('fk_trench_superseded_by', 'trench', type_='foreignkey')
    op.drop_column('trench', 'superseded_by')
    op.drop_constraint('fk_trench_import_batch_id', 'trench', type_='foreignkey')
    op.drop_column('trench', 'import_batch_id')
    op.drop_column('trench', 'hole_type')
    op.drop_column('trench', 'point_order')