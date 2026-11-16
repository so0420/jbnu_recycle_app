from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.database import get_db
from app.models import RaidAttempt, User
from app.services.game import economy, monsters
from app.services.game import raid as raid_svc
from app.services.game import region

router = APIRouter()


@router.get("/raid")
async def raid_status(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    unit = await raid_svc.user_unit(db, user)
    r = await raid_svc.current(db, unit)
    mine = (await db.execute(select(RaidAttempt.damage).where(RaidAttempt.raid_id == r.id,
                                                              RaidAttempt.user_id == user.id))).scalars().all()
    d = await economy.daily(db, user)
    out = {"unit": unit, "boss": raid_svc.boss_view(r.boss), "hp": r.hp, "max_hp": r.max_hp,
           "killed": r.killed_at is not None, "week_start": r.week_start.isoformat(),
           "next_boss": raid_svc.boss_view(raid_svc.next_boss()), "board": await raid_svc.board(db, r),
           "my_damage": sum(mine), "my_attempts": len(mine), "free_left": not d.free_raid_used,
           "tickets": user.tickets, "unlocked": economy.unlocked(user, "raid"),
           "party": [monsters.view(m) for m in await monsters.party(db, user)]}
    await db.commit()
    return out


@router.post("/raid/attempt")
async def attempt(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    r = await raid_svc.attempt(db, user)
    await db.commit()
    return r


@router.get("/regions")
async def standings(db: AsyncSession = Depends(get_db)):
    rows = await region.standings(db)
    await db.commit()
    return rows


@router.get("/regions/{unit}/feed")
async def feed(unit: str, db: AsyncSession = Depends(get_db)):
    return await region.feed(db, unit)
