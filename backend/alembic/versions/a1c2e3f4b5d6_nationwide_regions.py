"""nationwide regions, unique place key, consent & session columns

Revision ID: a1c2e3f4b5d6
Revises: d810d3c4c5dc
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c2e3f4b5d6"
down_revision = "d810d3c4c5dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("regions", "gu", existing_type=sa.String(20), type_=sa.String(40), existing_nullable=False)
    op.add_column("regions", sa.Column("sido", sa.String(20), nullable=False, server_default=""))
    op.add_column("regions", sa.Column("sigungu_code", sa.String(5), nullable=False, server_default=""))
    op.create_index("ix_regions_sido", "regions", ["sido"])
    op.create_index("ix_regions_sigungu_code", "regions", ["sigungu_code"])
    op.execute("UPDATE regions SET sido='전북특별자치도', sigungu_code=LEFT(code,5), gu=CONCAT('전주시 ', gu) "
               "WHERE code LIKE '5211%' AND gu NOT LIKE '전주시%'")
    # 같은 (source, source_id) 중복 행 정리: 인증 기록이 참조하지 않는 뒤쪽 행만 지운다
    op.execute("""
        DELETE p FROM places p
        JOIN places q ON p.source = q.source AND p.source_id = q.source_id AND p.id > q.id
        LEFT JOIN verifications v ON v.place_id = p.id
        WHERE v.id IS NULL
    """)
    op.create_unique_constraint("ux_places_source", "places", ["source", "source_id"])

    op.alter_column("users", "login_id", existing_type=sa.String(30), type_=sa.String(40), existing_nullable=False)
    op.add_column("users", sa.Column("age_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("agreed_location_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("policy_version", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
    op.drop_column("users", "policy_version")
    op.drop_column("users", "agreed_location_at")
    op.drop_column("users", "age_confirmed_at")
    op.drop_constraint("ux_places_source", "places", type_="unique")
    op.drop_index("ix_regions_sigungu_code", "regions")
    op.drop_index("ix_regions_sido", "regions")
    op.drop_column("regions", "sigungu_code")
    op.drop_column("regions", "sido")
    op.alter_column("regions", "gu", existing_type=sa.String(40), type_=sa.String(20), existing_nullable=False)
