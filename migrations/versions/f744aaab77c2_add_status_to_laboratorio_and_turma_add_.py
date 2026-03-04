"""add status to laboratorio and turma, add coordenador_id to turma

Revision ID: f744aaab77c2
Revises: 2f8e476440bc
Create Date: 2026-03-04 02:33:37.413359

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f744aaab77c2'
down_revision = '2f8e476440bc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('laboratorio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))

    # Preenche o valor default nos registros existentes
    op.execute("UPDATE laboratorio SET status = 'ativo' WHERE status IS NULL")

    with op.batch_alter_table('turma', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('coordenador_id', sa.Integer(), nullable=True))

    # Preenche o valor default nos registros existentes
    op.execute("UPDATE turma SET status = 'ativa' WHERE status IS NULL")


def downgrade():
    with op.batch_alter_table('turma', schema=None) as batch_op:
        batch_op.drop_column('coordenador_id')
        batch_op.drop_column('status')

    with op.batch_alter_table('laboratorio', schema=None) as batch_op:
        batch_op.drop_column('status')