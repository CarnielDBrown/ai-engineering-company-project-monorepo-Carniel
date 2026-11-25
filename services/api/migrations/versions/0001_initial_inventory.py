"""Create the initial inventory schema.

Revision ID: 0001_initial_inventory
Revises:
Create Date: 2026-10-09

This clean-install revision describes only the three inventory tables. It is not
an adoption/baseline migration for any existing database.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0001_initial_inventory"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create inventory catalogue and movement tables."""
    op.create_table(
        "medical_supplies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sku", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("unit", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("country", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medical_supplies_sku"), "medical_supplies", ["sku"], unique=True)

    op.create_table(
        "supply_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supply_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("vendor_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["supply_id"], ["medical_supplies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supply_deliveries_created_at"), "supply_deliveries", ["created_at"], unique=False)
    op.create_index(op.f("ix_supply_deliveries_supply_id"), "supply_deliveries", ["supply_id"], unique=False)

    op.create_table(
        "supply_consumptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supply_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("consumption_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["supply_id"], ["medical_supplies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supply_consumptions_created_at"), "supply_consumptions", ["created_at"], unique=False)
    op.create_index(op.f("ix_supply_consumptions_supply_id"), "supply_consumptions", ["supply_id"], unique=False)


def downgrade() -> None:
    """Refuse to drop inventory tables and their operational data."""
    raise RuntimeError(
        "Downgrading the initial inventory revision would delete inventory data. "
        "Use a reviewed forward migration or the documented recovery procedure."
    )
