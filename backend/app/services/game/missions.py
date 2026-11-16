"""일일·주간 미션."""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.clock import today
from app.services.game import data, economy, monsters


def _daily_pick(user: User) -> list[dict]:
    """하루 3개: 사용자·날짜로 정해지는 고정 순환 (새로고침해도 같음)."""
    all_ = data.economy()["missions"]["daily"]
    k = (user.id + today().toordinal()) % len(all_)
    picked = [all_[(k + i) % len(all_)] for i in range(3)]
    if not economy.unlocked(user, "raid"):
        picked = [m for m in picked if m["field"] != "raid_count"]
    if not economy.unlocked(user, "expedition"):
        picked = [m for m in picked if m["field"] != "expedition_sent"]
    return picked


async def status(db: AsyncSession, user: User) -> dict:
    d = await economy.daily(db, user)
    w = await economy.weekly(db, user)
    claimed = d.missions_claimed or []
    daily = [{**m, "progress": min(m["goal"], getattr(d, m["field"])), "claimed": m["id"] in claimed}
             for m in _daily_pick(user)]
    wprog = {"verify3": w.verify_count, "types3": len(w.types or []), "habit5": w.habit_count}
    weekly = [{**m, "progress": min(m["goal"], wprog[m["id"]]), "claimed": m["id"] in (w.claimed or [])}
              for m in data.economy()["missions"]["weekly"]]
    return {"daily": daily, "weekly": weekly, "unlocked": economy.unlocked(user, "missions"),
            "types3_material_pending": await _types3_pending(db, user) is not None,
            "reward_preview": {"daily_coins": economy.mult(data.economy()["missions"]["daily_reward"]["coins"]),
                               "daily_xp": economy.mult(data.economy()["missions"]["daily_reward"]["xp"]),
                               "weekly_materials": economy.mult(data.economy()["missions"]["weekly_materials"])}}


async def claim(db: AsyncSession, user: User, mission_id: str) -> dict:
    economy.require(user, "missions")
    cfg = data.economy()["missions"]
    st = await status(db, user)
    for m in st["daily"]:
        if m["id"] == mission_id:
            if m["claimed"] or m["progress"] < m["goal"]:
                raise HTTPException(400, "아직 받을 수 없어요")
            d = await economy.daily(db, user)
            d.missions_claimed = [*(d.missions_claimed or []), mission_id]
            out = {"coins": await economy.add_resource(db, user, "coins", cfg["daily_reward"]["coins"], "mission",
                                                       mission_id),
                   "xp": (await economy.add_xp(db, user, cfg["daily_reward"]["xp"], "mission", mission_id))["xp"]}
            if all(x["claimed"] or x["id"] == mission_id for x in st["daily"]) \
                    and "all_bonus" not in (d.missions_claimed or []):
                d.missions_claimed = [*(d.missions_claimed or []), "all_bonus"]
                out["tickets"] = await economy.add_resource(db, user, "tickets", cfg["daily_all_bonus_tickets"],
                                                            "mission_all")
            return out
    for m in st["weekly"]:
        if m["id"] == mission_id:
            if m["claimed"] or m["progress"] < m["goal"]:
                raise HTTPException(400, "아직 받을 수 없어요")
            w = await economy.weekly(db, user)
            w.claimed = [*(w.claimed or []), mission_id]
            if m["reward"] == "capsule":
                last = (w.types or [None])[-1]
                cap = await monsters.grant_capsule(db, user, last if last in data.BASE_TYPES else "plastic", "weekly")
                return {"capsule": {"id": cap.id, "type": cap.type}}
            return {"materials_choice": economy.mult(cfg["weekly_materials"])}
    raise HTTPException(404, "미션을 찾을 수 없어요")


async def _types3_pending(db: AsyncSession, user: User):
    """보상을 받았지만 재료를 아직 고르지 않은 주 (이번 주, 없으면 지난주: 일요일 밤에 받고 월요일에 골라도 되게)."""
    from datetime import timedelta
    from app.models import UserWeekly
    from app.services.clock import week_start
    for ws in (week_start(), week_start() - timedelta(days=7)):
        w = await db.get(UserWeekly, (user.id, ws))
        if w is not None and "types3" in (w.claimed or []) and "types3_mat" not in (w.claimed or []):
            return w
    return None


async def claim_weekly_materials(db: AsyncSession, user: User, material: str) -> dict:
    """types3 보상: 원하는 재료 30 (claim 뒤 한 번만)."""
    w = await _types3_pending(db, user)
    if w is None:
        raise HTTPException(400, "받을 수 있는 재료 보상이 없어요")
    if material not in data.BASE_TYPES:
        raise HTTPException(400, "재료를 골라 주세요")
    w.claimed = [*(w.claimed or []), "types3_mat"]
    got = await economy.add_resource(db, user, f"mat:{material}", data.economy()["missions"]["weekly_materials"],
                                     "weekly_types3")
    return {"material": material, "amount": got}
