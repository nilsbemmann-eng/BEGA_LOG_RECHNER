"""add skipped_irrelevant import job status

Revision ID: b2d3e4f5a6b7
Revises: a1c2d3e4f5a6
Create Date: 2026-10-15 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3e4f5a6b7'
down_revision: Union[str, None] = 'a1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE import_job_status ADD VALUE IF NOT EXISTS 'SKIPPED_IRRELEVANT'")
    else:
        with op.batch_alter_table("import_jobs") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.Enum(
                    "RUNNING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", name="import_job_status"
                ),
                type_=sa.Enum(
                    "RUNNING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "SKIPPED_IRRELEVANT",
                    name="import_job_status",
                ),
                existing_nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        with op.batch_alter_table("import_jobs") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.Enum(
                    "RUNNING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "SKIPPED_IRRELEVANT",
                    name="import_job_status",
                ),
                type_=sa.Enum(
                    "RUNNING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", name="import_job_status"
                ),
                existing_nullable=False,
            )
    # Postgres-Enum-Werte koennen nicht entfernt werden, ohne den Typ neu
    # anzulegen - 'SKIPPED_IRRELEVANT' bleibt beim Downgrade bewusst im
    # Enum-Typ bestehen (harmlos, solange keine solche Zeile mehr existiert).
