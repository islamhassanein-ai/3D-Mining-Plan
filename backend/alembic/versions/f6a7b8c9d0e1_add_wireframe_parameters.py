"""add_wireframe_parameters

``wireframe.parameters`` -- a nullable JSON column recording how a generated
solid was produced: threshold, search ellipsoid, sample-type weights, composite
length, and the validation report that came back.

A grade shell whose threshold and search orientation are unknown cannot be
reproduced, checked, or defended, which makes it useless for reporting -- and
reporting is the reason the feature exists. Imported wireframes leave this NULL;
they carry their provenance in whatever file they came from.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-08 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('wireframe', sa.Column('parameters', sa.JSON(), nullable=True))
    op.create_index('idx_wireframe_project_type', 'wireframe',
                    ['project_id', 'solid_type'])


def downgrade() -> None:
    op.drop_index('idx_wireframe_project_type', table_name='wireframe')
    op.drop_column('wireframe', 'parameters')
