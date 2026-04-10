"""add equipamento table

Revision ID: a3c1e2f5b8d9
Revises: f744aaab77c2
Create Date: 2026-04-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c1e2f5b8d9'
down_revision = '1d529f18c290'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'equipamento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('tipo', sa.String(length=50), nullable=True),
        sa.Column('patrimonio', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ativo'),
        sa.Column('laboratorio_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['laboratorio_id'], ['laboratorio.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patrimonio'),
    )


def downgrade():
    op.drop_table('equipamento')
