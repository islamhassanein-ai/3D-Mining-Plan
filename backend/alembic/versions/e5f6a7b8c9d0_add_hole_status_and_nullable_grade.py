"""add_hole_status_and_nullable_grade

Two related changes for the planned-borehole and unsampled-interval work:

* ``collar.hole_status`` -- 'drilled' (default) or 'planned', so proposed
  holes can be styled distinctly from completed ones. Existing rows backfill
  to 'drilled'.
* ``assay_interval.grade_value`` becomes NULLable. An interval that was
  logged but never assayed previously had to be stored as 0.0 g/t, which is
  indistinguishable from a genuine barren result. NULL now means "no assay",
  and the grade colour scale renders it as the Unsampled category.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-31 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('collar', sa.Column('hole_status', sa.String(length=10), nullable=True))
    op.execute("UPDATE collar SET hole_status = 'drilled' WHERE hole_status IS NULL")
    op.create_index('idx_collar_project_hole_status', 'collar', ['project_id', 'hole_status'])

    op.alter_column('assay_interval', 'grade_value',
                    existing_type=sa.Numeric(), nullable=True)


def downgrade() -> None:
    # Reinstating NOT NULL requires a concrete value; 0.0 is the pre-migration
    # representation of an unassayed interval.
    op.execute("UPDATE assay_interval SET grade_value = 0.0 WHERE grade_value IS NULL")
    op.alter_column('assay_interval', 'grade_value',
                    existing_type=sa.Numeric(), nullable=False)

    op.drop_index('idx_collar_project_hole_status', table_name='collar')
    op.drop_column('collar', 'hole_status')
