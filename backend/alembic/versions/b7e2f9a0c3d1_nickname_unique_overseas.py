"""닉네임 유일, 국외 이전 동의 시각

Revision ID: b7e2f9a0c3d1
Revises: a1c2e3f4b5d6
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e2f9a0c3d1"
down_revision = "a1c2e3f4b5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("agreed_overseas_at", sa.DateTime(), nullable=True))
    # 예전 가입자는 개인정보 동의 문구에 국외 이전이 함께 있었으므로 그 시각을 옮겨 둔다
    op.execute("UPDATE users SET agreed_overseas_at = agreed_terms_at WHERE agreed_overseas_at IS NULL")
    # 겹치는 닉네임은 뒤에 가입한 쪽에 번호를 붙인다
    op.execute("""
        UPDATE users u JOIN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY nickname ORDER BY id) AS rn FROM users
            ) t WHERE t.rn > 1
        ) d ON u.id = d.id
        SET u.nickname = LEFT(CONCAT(u.nickname, '#', u.id), 30)
    """)
    op.create_unique_constraint("uq_users_nickname", "users", ["nickname"])


def downgrade() -> None:
    op.drop_constraint("uq_users_nickname", "users", type_="unique")
    op.drop_column("users", "agreed_overseas_at")
