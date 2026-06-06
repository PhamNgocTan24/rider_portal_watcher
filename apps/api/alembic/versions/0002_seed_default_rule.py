"""seed_default_rule

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-07
"""
from __future__ import annotations

from alembic import op

revision: str = "0002"
down_revision: str = "0001"
branch_labels = None
depends_on = None

DEFAULT_RULE_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO business_rules (
            id, name,
            min_booking_value,
            allowed_pickup_locations,
            allowed_vehicle_categories,
            allowed_customer_categories,
            auto_accept, is_active,
            created_at, updated_at
        ) VALUES (
            '{DEFAULT_RULE_ID}',
            'Default Rule',
            50.00,
            ARRAY['Heathrow','Gatwick','Stansted','Luton','City Airport','Mayfair'],
            ARRAY['Executive Saloon','Saloon','MPV','Estate','Minibus'],
            ARRAY['corporate','leisure','vip'],
            false, true,
            now(), now()
        )
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute(f"DELETE FROM business_rules WHERE id = '{DEFAULT_RULE_ID}'")
