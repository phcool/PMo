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
    # 创建用户偏好表
    op.create_table(
        'user_preferences',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('preferences', JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=False)


def downgrade() -> None:
    # 删除用户偏好表
    op.drop_index(op.f('ix_user_preferences_user_id'), table_name='user_preferences')
    op.drop_table('user_preferences') 