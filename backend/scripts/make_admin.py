"""관리자 지정 (가입 때 자동으로 관리자가 되지 않게 따로 실행한다).

사용 (서버): docker exec recycle-app python -m scripts.make_admin <아이디> [--revoke]
"""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select  # noqa: E402

from app.database.session import AsyncSessionLocal  # noqa: E402
from app.models import User  # noqa: E402


async def main(login_id: str, revoke: bool) -> None:
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.login_id == login_id.lower()))).scalars().first()
        if u is None:
            sys.exit(f"없는 아이디: {login_id}")
        u.role = "user" if revoke else "admin"
        await db.commit()
        print(f"{u.login_id} → {u.role}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용: python -m scripts.make_admin <아이디> [--revoke]")
    asyncio.run(main(sys.argv[1], "--revoke" in sys.argv))
