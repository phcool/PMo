"""add_keywords_field

Revision ID: 4a98a354d057
Revises: e0ca28a97a8b
Create Date: 2025-04-18 06:24:12.014683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a98a354d057'
down_revision: Union[str, None] = 'e0ca28a97a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add keywords field to paper analysis table"""
    op.add_column('paper_analysis', sa.Column('keywords', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove keywords field from paper analysis table"""
    op.drop_column('paper_analysis', 'keywords')
