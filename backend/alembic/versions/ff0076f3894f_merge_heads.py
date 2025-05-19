"""merge heads

Revision ID: ff0076f3894f
Revises: e7976cb2cea9, remove_user_tables
Create Date: 2025-05-19 16:02:45.198043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff0076f3894f'
down_revision: Union[str, None] = ('e7976cb2cea9', 'remove_user_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
