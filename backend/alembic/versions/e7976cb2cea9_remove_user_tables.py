"""remove_user_tables

Revision ID: e7976cb2cea9
Revises: da9f1541b952
Create Date: 2025-05-19 15:56:08.149857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7976cb2cea9'
down_revision: Union[str, None] = 'da9f1541b952'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
