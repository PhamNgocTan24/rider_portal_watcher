"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-06
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # booking_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "booking_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_booking_id", sa.String(255), nullable=False),
        sa.Column("portal_name", sa.String(100), nullable=False),
        sa.Column("pickup_location", sa.Text(), nullable=True),
        sa.Column("dropoff_location", sa.Text(), nullable=True),
        sa.Column("booking_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("vehicle_category", sa.String(100), nullable=True),
        sa.Column("customer_category", sa.String(100), nullable=True),
        sa.Column("pickup_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="new"),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portal_name", "external_booking_id", name="uq_booking_portal_external_id"
        ),
    )
    op.create_index("ix_booking_jobs_external_booking_id", "booking_jobs", ["external_booking_id"])
    op.create_index("ix_booking_jobs_portal_name", "booking_jobs", ["portal_name"])
    op.create_index("ix_booking_jobs_status", "booking_jobs", ["status"])

    # ------------------------------------------------------------------
    # business_rules
    # ------------------------------------------------------------------
    op.create_table(
        "business_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("min_booking_value", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "allowed_pickup_locations",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column(
            "allowed_vehicle_categories",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column(
            "allowed_customer_categories",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column("auto_accept", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_rules_is_active", "business_rules", ["is_active"])

    # ------------------------------------------------------------------
    # automation_logs
    # ------------------------------------------------------------------
    op.create_table(
        "automation_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("portal_name", sa.String(100), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("step", sa.String(100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("external_booking_id", sa.String(255), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("html_snapshot_path", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_logs_portal_name", "automation_logs", ["portal_name"])
    op.create_index("ix_automation_logs_level", "automation_logs", ["level"])
    op.create_index("ix_automation_logs_step", "automation_logs", ["step"])
    op.create_index("ix_automation_logs_external_booking_id", "automation_logs", ["external_booking_id"])
    op.create_index("ix_automation_logs_created_at", "automation_logs", ["created_at"])

    # ------------------------------------------------------------------
    # portal_status
    # ------------------------------------------------------------------
    op.create_table(
        "portal_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("portal_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="healthy"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("auto_accept_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_name", name="uq_portal_status_portal_name"),
    )
    op.create_index("ix_portal_status_portal_name", "portal_status", ["portal_name"])


def downgrade() -> None:
    op.drop_table("portal_status")
    op.drop_table("automation_logs")
    op.drop_table("business_rules")
    op.drop_table("booking_jobs")
