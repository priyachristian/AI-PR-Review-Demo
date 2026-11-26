"""add company_id and migrate salary to numeric

Revision ID: 20261117_0002
Revises: 20261117_0001
Create Date: 2026-11-17 12:46:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261117_0002'
down_revision: Union[str, None] = '20261117_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.alter_column(
            'salary',
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=12, scale=2, asdecimal=True),
            existing_nullable=True,
        )
        batch_op.drop_index('ix_employees_email')
        batch_op.create_index('ix_employees_email', ['email'], unique=False)
        batch_op.create_index('ix_employees_company_id', ['company_id'], unique=False)
        batch_op.create_unique_constraint('uq_company_employee_email', ['company_id', 'email'])


def downgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_constraint('uq_company_employee_email', type_='unique')
        batch_op.drop_index('ix_employees_company_id')
        batch_op.drop_index('ix_employees_email')
        batch_op.create_index('ix_employees_email', ['email'], unique=True)
        batch_op.alter_column(
            'salary',
            existing_type=sa.Numeric(precision=12, scale=2, asdecimal=True),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.drop_column('company_id')
