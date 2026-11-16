"""관리자 지정 (가입 때 자동으로 관리자가 되지 않게 따로 실행한다).

사용 (서버):
  docker exec recycle-app python -m scripts.make_admin <아이디> [--revoke]
  docker exec -i recycle-app python -m scripts.make_admin <아이디> --create   (비밀번호는 표준 입력으로)
"""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select  # noqa: E402

from app.core.auth import hash_password  # noqa: E402
from app.database.session import AsyncSessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.services.clock import now  # noqa: E402


async def main(login_id: str, revoke: bool, create: bool) -> None:
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.login_id == login_id.lower()))).scalars().first()
        if u is not None and create:
            sys.exit(f"이미 있는 아이디라 만들지 않았어요 (관리자 지정도 하지 않음): {login_id}")
        if u is None and create:
            pw = sys.stdin.readline().strip()
            if not pw:
                sys.exit("비밀번호를 표준 입력으로 넣어 주세요")
            t = now()
            u = User(login_id=login_id.lower(), password_hash=hash_password(pw), nickname="관리자", role="admin",
                     agreed_terms_at=t, age_confirmed_at=t, agreed_location_at=t, agreed_overseas_at=t,
                     policy_version="admin",
                     token_version=0, xp=0, level=1, coins=0, tickets=0, crystals=0, bag_capacity=6, pity=0,
                     starter_done=False)
            db.add(u)
            await db.commit()
            print(f"{u.login_id} 생성 → admin")
            return
        if u is None:
            sys.exit(f"없는 아이디: {login_id}")
        u.role = "user" if revoke else "admin"
        await db.commit()
        print(f"{u.login_id} → {u.role}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용: python -m scripts.make_admin <아이디> [--revoke]")
    asyncio.run(main(sys.argv[1], "--revoke" in sys.argv, "--create" in sys.argv))
