"""remove user tables

Revision ID: remove_user_tables
Revises: da9f1541b952
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
import logging

# revision identifiers, used by Alembic.
revision = 'remove_user_tables'
down_revision = 'da9f1541b952'  # 指向最新的迁移
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

def upgrade() -> None:
    # 获取数据库连接
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()
    
    logger.info(f"Existing tables: {existing_tables}")
    
    # 先删除依赖表
    if 'user_paper_views' in existing_tables:
        logger.info("Dropping user_paper_views table...")
        op.execute('DROP TABLE IF EXISTS user_paper_views CASCADE')
    
    if 'user_search_history' in existing_tables:
        logger.info("Dropping user_search_history table...")
        op.execute('DROP TABLE IF EXISTS user_search_history CASCADE')
    
    # 最后删除主表
    logger.info("Dropping user table...")
    op.execute('DROP TABLE IF EXISTS "user" CASCADE')
    
    # 验证表是否被删除
    remaining_tables = inspector.get_table_names()
    logger.info(f"Remaining tables after migration: {remaining_tables}")

def downgrade() -> None:
    # 恢复 user 表（只包含 user_id 主键）
    op.create_table('user',
        sa.Column('user_id', sa.String(), primary_key=True)
    )
    # 恢复 user_search_history 表
    op.create_table('user_search_history',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
        sa.PrimaryKeyConstraint('user_id', 'query', 'timestamp')
    )
    # 恢复 user_paper_views 表
    op.create_table('user_paper_views',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('paper_id', sa.String(), nullable=False),
        sa.Column('view_date', sa.DateTime(), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=False),
        sa.Column('first_viewed_at', sa.DateTime(), nullable=False),
        sa.Column('last_viewed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
        sa.PrimaryKeyConstraint('user_id', 'paper_id')
    ) 