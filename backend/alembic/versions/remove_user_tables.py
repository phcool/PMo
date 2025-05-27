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
down_revision = 'da9f1541b952'  # Points to the latest migration
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

def upgrade() -> None:
    # Get database connection
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()
    
    logger.info(f"Existing tables: {existing_tables}")
    
    # Drop dependent tables first
    if 'user_paper_views' in existing_tables:
        logger.info("Dropping user_paper_views table...")
        op.execute('DROP TABLE IF EXISTS user_paper_views CASCADE')
    
    if 'user_search_history' in existing_tables:
        logger.info("Dropping user_search_history table...")
        op.execute('DROP TABLE IF EXISTS user_search_history CASCADE')
    
    # Finally, drop the main table
    logger.info("Dropping user table...")
    op.execute('DROP TABLE IF EXISTS "user" CASCADE')
    
    # Verify if tables are deleted
    remaining_tables = inspector.get_table_names()
    logger.info(f"Remaining tables after migration: {remaining_tables}")

def downgrade() -> None:
    # Restore user table (only includes user_id primary key)
    op.create_table('user',
        sa.Column('user_id', sa.String(), primary_key=True)
    )
    # Restore user_search_history table
    op.create_table('user_search_history',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
        sa.PrimaryKeyConstraint('user_id', 'query', 'timestamp')
    )
    # Restore user_paper_views table
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