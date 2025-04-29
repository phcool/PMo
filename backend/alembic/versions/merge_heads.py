"""merge multiple heads

Revision ID: merge_multiple_heads
Revises: 4a98a354d057, ee3dce9183af
Create Date: 2023-11-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_multiple_heads'
down_revision = ('4a98a354d057', 'ee3dce9183af')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 