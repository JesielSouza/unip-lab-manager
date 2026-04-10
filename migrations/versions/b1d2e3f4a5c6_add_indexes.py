"""add indexes on reserva_lab

Revision ID: b1d2e3f4a5c6
Revises: a3c1e2f5b8d9
Create Date: 2026-04-10 00:01:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b1d2e3f4a5c6'
down_revision = 'a3c1e2f5b8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reserva_lab') as batch_op:
        batch_op.create_index('ix_reserva_lab_laboratorio_id', ['laboratorio_id'])
        batch_op.create_index('ix_reserva_lab_turma_id', ['turma_id'])
        batch_op.create_index('ix_reserva_lab_data', ['data'])
        batch_op.create_index('ix_reserva_lab_status', ['status'])
        batch_op.create_index('ix_reserva_lab_usuario_id', ['usuario_id'])


def downgrade():
    with op.batch_alter_table('reserva_lab') as batch_op:
        batch_op.drop_index('ix_reserva_lab_laboratorio_id')
        batch_op.drop_index('ix_reserva_lab_turma_id')
        batch_op.drop_index('ix_reserva_lab_data')
        batch_op.drop_index('ix_reserva_lab_status')
        batch_op.drop_index('ix_reserva_lab_usuario_id')
