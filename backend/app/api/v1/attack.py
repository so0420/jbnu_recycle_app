from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.security import limiter
from app.database import get_db
from app.models import User
from app.services import locks
from app.services.game import attack as attack_svc

router = APIRouter()


@router.get("/attack")
async def overview(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    """지역 공방전 화면: 우리 지역, 공격권, 공격할 수 있는 지역과 예상 피해."""
    out = await attack_svc.overview(db, user)
    await db.commit()
    return out


class AttackIn(BaseModel):
    target: str = Field(min_length=1, max_length=12)


@router.post("/attack")
@limiter.limit("20/minute")
async def attack(request: Request, body: AttackIn, user: User = Depends(auth.current_user),
                 db: AsyncSession = Depends(get_db)):
    user = await locks.lock_user(db, user)      # 공격권을 동시에 두 번 쓰지 않게
    out = await attack_svc.attack(db, user, body.target)
    await db.commit()
    return out
