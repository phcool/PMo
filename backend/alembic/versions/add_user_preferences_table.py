"""add user preferences table

Revision ID: add_user_preferences_table
Revises: 86c7f7e9b13d
Create Date: 2023-11-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'ee3dce9183af'
down_revision = '86c7f7e9b13d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('ip_prefix', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_visited_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_preferences_ip_prefix'), 'user_preferences', ['ip_prefix'], unique=False)


def downgrade() -> None:
    # Delete user preferences table
    op.drop_index(op.f('ix_user_preferences_ip_prefix'), table_name='user_preferences')
    op.drop_index(op.f('ix_user_preferences_user_id'), table_name='user_preferences')
    op.drop_table('user_preferences') 