"""동시 요청 직렬화.

같은 사용자의 보상·소비 요청은 users 행을 FOR UPDATE 로 잠가 한 번에 하나씩 처리한다.
DB 격리 수준이 READ COMMITTED 라서 잠금을 얻은 뒤의 조회는 다른 요청이 커밋한 최신 값을 본다.
populate_existing 으로 이미 세션에 올라온 객체도 새 값으로 덮어쓴다.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def lock_user(db: AsyncSession, user: User) -> User:
    q = select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    return (await db.execute(q)).scalars().one()


async def refresh_locked(db: AsyncSession, obj, lock: bool = True):
    """세션에 있는 객체를 DB 최신 값으로 다시 읽는다(필요하면 잠금)."""
    await db.refresh(obj, with_for_update=lock)
    return obj
