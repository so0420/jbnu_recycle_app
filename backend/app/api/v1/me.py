from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.config import settings
from app.database import get_db
from app.models import BagItem, ClassifyLog, Region, RegionEvent, User, Verification
from app.services import locks
from app.services.clock import now
from app.services.game import actions, data, economy, region

router = APIRouter()


async def profile(db: AsyncSession, user: User) -> dict:
    home = await db.get(Region, user.region_code) if user.region_code else None
    cur, need = economy.xp_progress(user.xp)
    d = await economy.daily(db, user)
    unit = region.unit_of(home)
    from app.models import RegionState
    from app.services.clock import week_start
    st = await db.get(RegionState, (week_start(), unit)) if unit else None     # 화면을 연다고 행을 만들지 않는다
    clean = st.cleanliness if st else float(region.cfg()["start"])
    units = await region.units(db) if unit else {}
    t = now()
    nxt = actions.next_dump_window(home, t)
    return {
        "id": user.id, "login_id": user.login_id, "nickname": user.nickname, "role": user.role,
        "level": user.level, "xp": user.xp, "xp_in_level": cur, "xp_need": need,
        "garden_stage": economy.garden_stage(user.level),
        "coins": user.coins, "tickets": user.tickets, "ticket_cap": data.economy()["tickets"]["cap"],
        "attack_tickets": user.attack_tickets or 0, "attack_ticket_cap": data.economy()["attack"]["cap"],
        "crystals": user.crystals, "materials": await economy.materials(db, user),
        "bag": {"count": await actions.bag_count(db, user), "capacity": economy.bag_capacity(user)},
        "starter_done": user.starter_done,
        "region": ({"code": home.code, "name": home.name, "gu": home.gu, "sido": home.sido,
                    "confirmed": bool(user.region_confirmed_at),
                    "unit": unit, "unit_name": units.get(unit, {}).get("name") if unit else None,
                    "cleanliness": round(clean) if unit else None,
                    "stage": region.stage_of(clean) if unit else None,
                    "center": [home.center_lat, home.center_lng],
                    "next_change_free": user.region_changed_at is None,
                    "dump_weekdays": home.dump_weekdays,
                    "dump_schedule": actions.dump_schedule(home),
                    "attacked_today": await _attacked_today(db, unit)} if home else None),
        "today": {"verify_count": d.verify_count, "verify_reward_left": max(0, 3 - d.verify_count),
                  "scan_xp_left": max(0, data.economy()["account_xp"]["scan_daily_cap"] - d.guide_xp_count),
                  "free_raid": not d.free_raid_used, "dumpday_ticket_taken": d.dumpday_ticket,
                  "dump_time_now": actions.is_dump_time(home, t),
                  "next_dump_at": nxt.isoformat() if nxt else None,
                  "dump_items": actions.dump_items_for(home, t)},
        "unlocks": {k: economy.unlocked(user, k) for k in data.economy()["garden"]},
        "unlock_levels": data.economy()["garden"],
        "economy_multiplier": settings.ECONOMY_MULTIPLIER,
    }


async def _attacked_today(db: AsyncSession, unit: str | None) -> dict:
    """오늘 우리 지역이 받은 공격 (횟수, 피해 합)."""
    if not unit:
        return {"count": 0, "amount": 0}
    from datetime import datetime, time as dtime
    from sqlalchemy import func
    from app.services.clock import today
    n, amt = (await db.execute(select(func.count(), func.coalesce(func.sum(-RegionEvent.amount), 0)).where(
        RegionEvent.unit == unit, RegionEvent.type == "attack",
        RegionEvent.created_at >= datetime.combine(today(), dtime.min)))).one()
    return {"count": int(n), "amount": round(float(amt))}


@router.get("")
async def me(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    out = await profile(db, user)
    await db.commit()
    return out


class RegionIn(BaseModel):
    region_code: str


@router.patch("/region")
async def change_region(body: RegionIn, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    user = await locks.lock_user(db, user)
    r = await db.get(Region, body.region_code)
    if r is None:
        raise HTTPException(400, "동네를 다시 골라 주세요")
    if user.region_changed_at and now() - user.region_changed_at < timedelta(days=30):
        left = 30 - (now() - user.region_changed_at).days
        raise HTTPException(400, f"동네는 30일에 한 번 바꿀 수 있어요 ({left}일 남음)")
    if user.region_code and user.region_confirmed_at:
        # 확정 뒤 첫 변경은 그대로 (가입 때 잘못 고른 경우), 그다음부터는 30일에 한 번 + 도전권 초기화
        if user.region_changed_at is not None:
            user.tickets = 0
            user.attack_tickets = 0
        user.region_changed_at = now()
    user.region_code = r.code
    await db.commit()
    return {"ok": True}


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=72)


@router.post("/password")
async def change_password(body: PasswordIn, response: Response, user: User = Depends(auth.current_user),
                          db: AsyncSession = Depends(get_db)):
    if not await auth.verify_password_async(body.current, user.password_hash):
        raise HTTPException(400, "지금 비밀번호가 맞지 않아요")
    if not auth.password_ok(body.new):
        raise HTTPException(400, auth.PASSWORD_RULE)
    user.password_hash = await auth.hash_password_async(body.new)
    user.token_version = (user.token_version or 0) + 1      # 다른 기기의 세션은 끊고
    await db.commit()
    auth.issue(response, user)                              # 이 기기는 새 세션으로 유지
    return {"ok": True}


@router.get("/history")
async def history(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    vs = (await db.execute(select(Verification).where(Verification.user_id == user.id)
                           .order_by(Verification.id.desc()).limit(50))).scalars()
    return [{"id": v.id, "at": v.created_at.isoformat(), "result": v.result, "fail_code": v.fail_code,
             "place_id": v.place_id, "distance_m": v.distance_m} for v in vs]


class DeleteIn(BaseModel):
    password: str


@router.post("/delete")
async def delete_account(body: DeleteIn, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    """회원 탈퇴: 사진 파일 삭제, 위치 기록 제거, 계정·닉네임 비식별화."""
    if not await auth.verify_password_async(body.password, user.password_hash):
        raise HTTPException(400, "비밀번호가 맞지 않아요")
    user = await locks.lock_user(db, user)
    paths = [p for (p,) in (await db.execute(select(ClassifyLog.photo_path).where(ClassifyLog.user_id == user.id)))]
    paths += [p for (p,) in (await db.execute(select(Verification.photo_path).where(Verification.user_id == user.id)))]
    await db.execute(update(ClassifyLog).where(ClassifyLog.user_id == user.id).values(photo_path=""))
    await db.execute(update(Verification).where(Verification.user_id == user.id)
                     .values(photo_path="", lat=0, lng=0, accuracy=0, distance_m=None, reward_json=None))
    await db.execute(update(RegionEvent).where(RegionEvent.user_id == user.id).values(nickname=None))
    await db.execute(delete(BagItem).where(BagItem.user_id == user.id))
    user.deleted_at = now()
    user.login_id = f"#deleted:{user.id}"          # 가입 규칙상 만들 수 없는 값
    user.nickname = f"#탈퇴{user.id}"
    user.password_hash = "!"
    user.token_version = (user.token_version or 0) + 1
    user.last_lat = user.last_lng = None
    await db.commit()
    for p in paths:                                  # 커밋이 성공한 뒤에 파일을 지운다
        if p:
            Path(settings.UPLOAD_DIR, p).unlink(missing_ok=True)
    return {"ok": True}
