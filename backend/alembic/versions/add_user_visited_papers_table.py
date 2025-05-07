"""Add user visited papers table

Revision ID: 54c7d8e9f123
Revises: ff4c6a9b3d12
Create Date: 2023-08-15 10:08:48.641742

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54c7d8e9f123'
down_revision = 'ff4c6a9b3d12'
branch_labels = None
depends_on = None


def upgrade():
    # Create user visited papers records table
    op.create_table(
        'user_visited_papers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('paper_id', sa.String(), nullable=False),
        sa.Column('visited_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_visited_papers_id'), 'user_visited_papers', ['id'], unique=False)
    op.create_index(op.f('ix_user_visited_papers_user_id'), 'user_visited_papers', ['user_id'], unique=False)


def downgrade():
    # Delete table and indexes
    op.drop_index(op.f('ix_user_visited_papers_user_id'), table_name='user_visited_papers')
    op.drop_index(op.f('ix_user_visited_papers_id'), table_name='user_visited_papers')
    op.drop_table('user_visited_papers') 