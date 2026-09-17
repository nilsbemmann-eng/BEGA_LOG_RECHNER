"""add preisadmin role and master-data versioning

Revision ID: a1c2d3e4f5a6
Revises: 00bbc2243ec1
Create Date: 2026-09-17 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5a6'
down_revision: Union[str, None] = '00bbc2243ec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'PREISADMIN'")
    else:
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "role",
                existing_type=sa.Enum("ADMIN", "PRUEFER", "VIEWER", name="user_role"),
                type_=sa.Enum("ADMIN", "PREISADMIN", "PRUEFER", "VIEWER", name="user_role"),
                existing_nullable=False,
            )

    op.add_column(
        "special_agreement_surcharges",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "special_agreement_surcharges",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.drop_index(op.f("ix_special_agreement_surcharges_tour_number_prefix"), table_name="special_agreement_surcharges")
    op.create_index(
        op.f("ix_special_agreement_surcharges_tour_number_prefix"),
        "special_agreement_surcharges", ["tour_number_prefix"], unique=False,
    )
    op.create_index(
        "ux_special_agreement_surcharges_current_prefix",
        "special_agreement_surcharges", ["tour_number_prefix"], unique=True,
        sqlite_where=sa.text("is_current"), postgresql_where=sa.text("is_current"),
    )

    op.add_column(
        "tour_origin_mappings",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "tour_origin_mappings",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ux_tour_origin_mappings_current_prefix_matchcode",
        "tour_origin_mappings", ["tour_number_prefix", "matchcode"], unique=True,
        sqlite_where=sa.text("is_current"), postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("ux_tour_origin_mappings_current_prefix_matchcode", table_name="tour_origin_mappings")
    op.drop_column("tour_origin_mappings", "is_current")
    op.drop_column("tour_origin_mappings", "version")

    op.drop_index("ux_special_agreement_surcharges_current_prefix", table_name="special_agreement_surcharges")
    op.drop_index(op.f("ix_special_agreement_surcharges_tour_number_prefix"), table_name="special_agreement_surcharges")
    op.create_index(
        op.f("ix_special_agreement_surcharges_tour_number_prefix"),
        "special_agreement_surcharges", ["tour_number_prefix"], unique=True,
    )
    op.drop_column("special_agreement_surcharges", "is_current")
    op.drop_column("special_agreement_surcharges", "version")

    # Postgres-Enum-Werte koennen nicht entfernt werden, ohne den Typ neu
    # anzulegen - 'PREISADMIN' bleibt beim Downgrade bewusst im Enum-Typ
    # bestehen (harmlos, solange kein Nutzer diese Rolle mehr hat).
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "role",
                existing_type=sa.Enum("ADMIN", "PREISADMIN", "PRUEFER", "VIEWER", name="user_role"),
                type_=sa.Enum("ADMIN", "PRUEFER", "VIEWER", name="user_role"),
                existing_nullable=False,
            )
