"""Add the centralized incident register and audit events.

Revision ID: 0002_incident_manager
Revises: 0001_initial_inventory
Create Date: 2026-10-26

This is an additive migration for an isolated, reviewed deployment target.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0002_incident_manager"
down_revision: Union[str, Sequence[str], None] = "0001_initial_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "managed_incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("branch", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("origin", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("corrective_action", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_by_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("source_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_managed_incidents_title"), "managed_incidents", ["title"], unique=False)
    op.create_index(op.f("ix_managed_incidents_category"), "managed_incidents", ["category"], unique=False)
    op.create_index(op.f("ix_managed_incidents_branch"), "managed_incidents", ["branch"], unique=False)
    op.create_index(op.f("ix_managed_incidents_status"), "managed_incidents", ["status"], unique=False)
    op.create_index(op.f("ix_managed_incidents_origin"), "managed_incidents", ["origin"], unique=False)
    op.create_index(op.f("ix_managed_incidents_is_critical"), "managed_incidents", ["is_critical"], unique=False)
    op.create_index(op.f("ix_managed_incidents_created_at"), "managed_incidents", ["created_at"], unique=False)
    op.create_index(op.f("ix_managed_incidents_source_key"), "managed_incidents", ["source_key"], unique=True)

    op.create_table(
        "incident_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("from_status", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("to_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["managed_incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incident_audit_events_incident_id"), "incident_audit_events", ["incident_id"], unique=False)
    op.create_index(op.f("ix_incident_audit_events_created_at"), "incident_audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading the incident-manager revision would delete incident and audit data. "
        "Use a reviewed forward migration or the documented recovery procedure."
    )