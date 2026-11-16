"""동시 요청 직렬화.

같은 사용자의 보상·소비 요청은 users 행을 FOR UPDATE 로 잠가 한 번에 하나씩 처리한다.
DB 격리 수준이 READ COMMITTED 라서 잠금을 얻은 뒤의 조회는 다른 요청이 커밋한 최신 값을 본다.
populate_existing 으로 이미 세션에 올라온 객체도 새 값으로 덮어쓴다.
"""
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HabitProgress, User, UserDaily, UserMaterial, UserWeekly

# 커밋 뒤에도 세션에 남는 사용자별 카운터 행: 잠금을 얻은 뒤 반드시 DB 값으로 다시 읽는다
_COUNTERS = (UserDaily, UserWeekly, HabitProgress, UserMaterial)


def _uid(user: User | int) -> int:
    """롤백으로 만료된 객체에서도 DB 를 다시 읽지 않고 기본키를 얻는다."""
    if isinstance(user, int):
        return user
    ident = inspect(user).identity
    return ident[0] if ident else user.id


async def lock_user(db: AsyncSession, user: User | int) -> User:
    q = select(User).where(User.id == _uid(user)).with_for_update().execution_options(populate_existing=True)
    u = (await db.execute(q)).scalars().one()
    if u.deleted_at is not None:
        from fastapi import HTTPException
        await db.rollback()
        raise HTTPException(401, "다시 로그인해 주세요")
    # expire_on_commit=False 라서 앞 단계(예: AI 사용 예약)에서 읽은 행이 옛 값으로 남아 있을 수 있다
    for obj in [o for o in list(db.identity_map.values()) if isinstance(o, _COUNTERS)]:
        st = inspect(obj)
        if st.dict.get("user_id") != u.id or st.deleted or st.detached:
            continue
        try:
            await db.refresh(obj)
        except Exception:          # 그새 지워진 행
            db.expunge(obj)
    return u


async def refresh_locked(db: AsyncSession, obj, lock: bool = True):
    """세션에 있는 객체를 DB 최신 값으로 다시 읽는다(필요하면 잠금)."""
    await db.refresh(obj, with_for_update=lock)
    return obj
