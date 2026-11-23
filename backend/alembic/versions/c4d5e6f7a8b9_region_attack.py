"""지역 공방전: 공격권, 공격한 지역 기록

Revision ID: c4d5e6f7a8b9
Revises: b7e2f9a0c3d1
"""
import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b7e2f9a0c3d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("attack_tickets", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("region_events", sa.Column("src_unit", sa.String(12), nullable=True))
    op.create_index("ix_region_events_src_unit", "region_events", ["src_unit"])


def downgrade() -> None:
    op.drop_index("ix_region_events_src_unit", table_name="region_events")
    op.drop_column("region_events", "src_unit")
    op.drop_column("users", "attack_tickets")
