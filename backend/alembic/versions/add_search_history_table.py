"""add search history table

Revision ID: add_search_history_table
Revises: merge_multiple_heads
Create Date: 2023-11-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ff4c6a9b3d12'
down_revision = 'merge_multiple_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建用户搜索历史表
    op.create_table(
        'user_search_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_search_history_id'), 'user_search_history', ['id'], unique=False)
    op.create_index(op.f('ix_user_search_history_user_id'), 'user_search_history', ['user_id'], unique=False)


def downgrade() -> None:
    # 删除用户搜索历史表
    op.drop_index(op.f('ix_user_search_history_user_id'), table_name='user_search_history')
    op.drop_index(op.f('ix_user_search_history_id'), table_name='user_search_history')
    op.drop_table('user_search_history') 