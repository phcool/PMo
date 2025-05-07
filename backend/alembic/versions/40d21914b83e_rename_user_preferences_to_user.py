"""rename_user_preferences_to_user

Revision ID: 40d21914b83e
Revises: f0481b28dab6
Create Date: 2025-05-07 03:56:42.943751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '40d21914b83e'
down_revision: Union[str, None] = 'f0481b28dab6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 使用重命名而不是删除和创建，保留数据
    op.rename_table('user_preferences', 'user')
    
    # 重命名索引 - 在PostgreSQL中，需要手动删除和重新创建索引
    op.drop_index('ix_user_preferences_ip_prefix', table_name='user')
    op.drop_index('ix_user_preferences_user_id', table_name='user')
    op.create_index(op.f('ix_user_ip_prefix'), 'user', ['ip_prefix'], unique=False)
    op.create_index(op.f('ix_user_user_id'), 'user', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 在回滚时，将表再次重命名回原名
    # 重命名索引
    op.drop_index(op.f('ix_user_ip_prefix'), table_name='user')
    op.drop_index(op.f('ix_user_user_id'), table_name='user')
    
    op.rename_table('user', 'user_preferences')
    
    # 重新创建原索引
    op.create_index('ix_user_preferences_ip_prefix', 'user_preferences', ['ip_prefix'], unique=False)
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'], unique=False)
