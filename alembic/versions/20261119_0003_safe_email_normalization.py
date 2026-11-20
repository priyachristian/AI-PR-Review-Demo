"""safe email normalization

Revision ID: 20261119_0003
Revises: 20261117_0002
Create Date: 2026-11-19 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261119_0003'
down_revision: Union[str, None] = '20261117_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Detect existing normalized duplicates before updating or creating constraints
    check_query = sa.text("""
        SELECT company_id, LOWER(TRIM(email)) AS norm_email, COUNT(*) AS cnt
        FROM employees
        GROUP BY company_id, LOWER(TRIM(email))
        HAVING COUNT(*) > 1
    """)
    duplicates = conn.execute(check_query).fetchall()
    if duplicates:
        conflicts = [
            f"company_id={row[0]}, email='{row[1]}' (count={row[2]})"
            for row in duplicates
        ]
        raise RuntimeError(
            f"Cannot safely normalize emails: duplicate records detected after normalization: {', '.join(conflicts)}. "
            "Conflicting employee records will not be silently deleted. Please resolve these conflicts before migrating."
        )

    # Safely normalize all emails to trimmed lowercase
    conn.execute(sa.text("UPDATE employees SET email = LOWER(TRIM(email))"))


def downgrade() -> None:
    pass
