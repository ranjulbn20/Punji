"""add_scheme_code_to_mutual_funds

Revision ID: cf7189e3dd02
Revises: e3a1f9c2d4b5
Create Date: 2026-06-13 20:18:40.378740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'cf7189e3dd02'
down_revision: Union[str, None] = 'e3a1f9c2d4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mutual_funds', sa.Column('scheme_code', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('mutual_funds', 'scheme_code')
