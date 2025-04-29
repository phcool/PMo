"""Remove user visited papers table

Revision ID: 8a7c5b9e2f01
Revises: 54c7d8e9f123
Create Date: 2023-09-01 15:08:48.641742

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a7c5b9e2f01'
down_revision = '54c7d8e9f123'
branch_labels = None
depends_on = None


def upgrade():
    # 删除表和索引
    op.drop_index(op.f('ix_user_visited_papers_user_id'), table_name='user_visited_papers')
    op.drop_index(op.f('ix_user_visited_papers_id'), table_name='user_visited_papers')
    op.drop_table('user_visited_papers')


def downgrade():
    # 重新创建用户访问过的论文记录表
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