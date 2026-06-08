"""add usuario reset token and dark mode columns

Revision ID: b7c9d2e4f6a1
Revises: a3c1e2f5b8d9
Create Date: 2026-06-08 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c9d2e4f6a1'
down_revision = 'a3c1e2f5b8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reset_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('reset_token_expiry', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('dark_mode', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('dark_mode')
        batch_op.drop_column('reset_token_expiry')
        batch_op.drop_column('reset_token')
