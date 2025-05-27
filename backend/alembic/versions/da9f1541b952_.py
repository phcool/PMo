"""empty message

Revision ID: da9f1541b952
Revises: 
Create Date: 2025-05-15 11:30:00.730409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'da9f1541b952'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('authors',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_authors_name'), 'authors', ['name'], unique=True)
    op.create_table('categories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True)
    op.create_table('papers',
    sa.Column('paper_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('abstract', sa.Text(), nullable=False),
    sa.Column('pdf_url', sa.String(), nullable=False),
    sa.Column('published_date', sa.DateTime(), nullable=False),
    sa.Column('updated_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('paper_id')
    )
    op.create_index(op.f('ix_papers_paper_id'), 'papers', ['paper_id'], unique=False)
    op.create_table('user',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('ip_prefix', sa.String(), nullable=True),
    sa.Column('last_visited_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_user_ip_prefix'), 'user', ['ip_prefix'], unique=False)
    op.create_index(op.f('ix_user_user_id'), 'user', ['user_id'], unique=False)
    op.create_table('user_search_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('query', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_search_history_id'), 'user_search_history', ['id'], unique=False)
    op.create_index(op.f('ix_user_search_history_user_id'), 'user_search_history', ['user_id'], unique=False)
    op.create_table('paper_authors',
    sa.Column('paper_id', sa.String(), nullable=False),
    sa.Column('author', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['author'], ['authors.name'], ),
    sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], ),
    sa.PrimaryKeyConstraint('paper_id', 'author')
    )
    op.create_table('paper_categories',
    sa.Column('paper_id', sa.String(), nullable=False),
    sa.Column('category', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['category'], ['categories.name'], ),
    sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], ),
    sa.PrimaryKeyConstraint('paper_id', 'category')
    )
    op.create_table('user_paper_views',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('paper_id', sa.String(), nullable=False),
    sa.Column('view_date', sa.Date(), nullable=False),
    sa.Column('first_viewed_at', sa.DateTime(), nullable=False),
    sa.Column('last_viewed_at', sa.DateTime(), nullable=False),
    sa.Column('view_count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_paper_views_id'), 'user_paper_views', ['id'], unique=False)
    op.create_index(op.f('ix_user_paper_views_paper_id'), 'user_paper_views', ['paper_id'], unique=False)
    op.create_index(op.f('ix_user_paper_views_user_id'), 'user_paper_views', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_paper_views_view_date'), 'user_paper_views', ['view_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_user_paper_views_view_date'), table_name='user_paper_views')
    op.drop_index(op.f('ix_user_paper_views_user_id'), table_name='user_paper_views')
    op.drop_index(op.f('ix_user_paper_views_paper_id'), table_name='user_paper_views')
    op.drop_index(op.f('ix_user_paper_views_id'), table_name='user_paper_views')
    op.drop_table('user_paper_views')
    op.drop_table('paper_categories')
    op.drop_table('paper_authors')
    op.drop_index(op.f('ix_user_search_history_user_id'), table_name='user_search_history')
    op.drop_index(op.f('ix_user_search_history_id'), table_name='user_search_history')
    op.drop_table('user_search_history')
    op.drop_index(op.f('ix_user_user_id'), table_name='user')
    op.drop_index(op.f('ix_user_ip_prefix'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_papers_paper_id'), table_name='papers')
    op.drop_table('papers')
    op.drop_index(op.f('ix_categories_name'), table_name='categories')
    op.drop_table('categories')
    op.drop_index(op.f('ix_authors_name'), table_name='authors')
    op.drop_table('authors')
