"""동 레이드: 주간 보스, 비동기 협동 체력 깎기, 처치 보상."""
import random
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassifyLog, Raid, RaidAttempt, Region, User, UserMonster, Verification
from app.services.clock import now, week_start
from app.services.game import battle, data, economy, monsters, region

DEFAULT_ATTEMPT_DAMAGE = 1500     # 파티 정보가 없는 활성 사용자 1명의 1회 예상 피해
ATTEMPTS_PER_USER = 7             # 3.5일 × 하루 2회 → 보통 참여율이면 3~4일 안에 처치


def boss_of_week(ws=None) -> str:
    ws = ws or week_start()
    order = data.bosses()["order"]
    return order[(ws.toordinal() // 7) % len(order)]


def next_boss() -> str:
    return boss_of_week(week_start() + timedelta(days=7))


async def _unit_users(db: AsyncSession, unit: str) -> list[User]:
    us = await region.units(db)
    codes = us.get(unit, {}).get("regions", [])
    if not codes:
        return []
    return list((await db.execute(select(User).where(User.region_code.in_(codes), User.deleted_at.is_(None)))).scalars())


async def _active_users(db: AsyncSession, users: list[User]) -> list[User]:
    since = now() - timedelta(days=7)
    out = []
    for u in users:
        v = (await db.execute(select(func.count()).select_from(Verification).where(
            Verification.user_id == u.id, Verification.created_at >= since))).scalar_one()
        c = (await db.execute(select(func.count()).select_from(ClassifyLog).where(
            ClassifyLog.user_id == u.id, ClassifyLog.created_at >= since))).scalar_one()
        if v or c:
            out.append(u)
    return out


async def party_units(db: AsyncSession, user: User) -> list[battle.Unit]:
    ms = await monsters.party(db, user)
    return [battle.make_ally(f"a{m.id}", monsters.view(m), m.slot == 0) for m in ms]


async def estimate_damage(db: AsyncSession, user: User, boss: str) -> float:
    party = await party_units(db, user)
    if not party:
        return DEFAULT_ATTEMPT_DAMAGE * 0.3
    total = 0
    for seed in range(5):
        party = await party_units(db, user)
        total += battle.simulate(party, boss, 1e12, seed).damage
    return total / 5


async def current(db: AsyncSession, unit: str) -> Raid:
    ws = week_start()
    raid = (await db.execute(select(Raid).where(Raid.unit == unit, Raid.week_start == ws))).scalars().first()
    if raid:
        return raid
    boss = boss_of_week(ws)
    cfg = data.economy()["raid"]
    active = await _active_users(db, await _unit_users(db, unit))
    est = 0.0
    for u in active:
        est += await estimate_damage(db, u, boss)
    missing = max(0, cfg["min_active"] - len(active))
    est += missing * DEFAULT_ATTEMPT_DAMAGE
    hp = int(max(5000, est * ATTEMPTS_PER_USER))
    raid = Raid(unit=unit, boss=boss, week_start=ws, max_hp=hp, hp=hp)
    db.add(raid)
    await db.flush()
    return raid


async def user_unit(db: AsyncSession, user: User) -> str:
    if not user.region_code:
        raise HTTPException(400, "내 동네를 먼저 정해 주세요")
    r = await db.get(Region, user.region_code)
    unit = region.unit_of(r)
    if not unit:
        raise HTTPException(400, "내 동네가 대전 지역에 속하지 않습니다")
    return unit


async def attempt(db: AsyncSession, user: User) -> dict:
    economy.require(user, "raid")
    unit = await user_unit(db, user)
    raid = await current(db, unit)
    if raid.killed_at:
        raise HTTPException(400, "이번 주 보스는 이미 쓰러졌어요. 다음 주 보스를 기다려 주세요")
    party = await party_units(db, user)
    if not party:
        raise HTTPException(400, "파티에 리몬을 넣어 주세요")
    d = await economy.daily(db, user)
    used_free = False
    if not d.free_raid_used:
        d.free_raid_used = True
        used_free = True
    else:
        await economy.add_resource(db, user, "tickets", -1, "raid", str(raid.id))

    # 동시 도전 대비: 보스 행을 잠그고 남은 체력을 다시 읽는다
    raid = (await db.execute(select(Raid).where(Raid.id == raid.id).with_for_update())).scalars().one()
    seed = random.randrange(1, 2 ** 31)
    res = battle.simulate(party, raid.boss, float(raid.hp), seed, boss_hp_ratio=raid.hp / raid.max_hp)
    dmg = min(res.damage, raid.hp)
    raid.hp -= dmg
    db.add(RaidAttempt(raid_id=raid.id, user_id=user.id, damage=dmg, seed=seed,
                       log_json={"units": res.units, "log": res.log}))
    d.raid_count += 1
    cfg = data.economy()["raid"]
    reward = {
        "coins": await economy.add_resource(db, user, "coins", cfg["reward_coins_per_attempt"], "raid", str(raid.id)),
        "materials": {},
    }
    for m in await monsters.party(db, user):
        t = data.line(m.species)["type"]
        if t in data.MATERIALS:
            got = await economy.add_resource(db, user, f"mat:{t}", cfg["reward_materials_per_attempt"], "raid",
                                             str(raid.id))
            reward["materials"][t] = reward["materials"].get(t, 0) + got
    if (await economy.daily(db, user)).raid_count == 1:
        reward["xp"] = (await economy.add_xp(db, user, data.economy()["account_xp"]["raid_daily"], "raid"))["xp"]
    killed = False
    if raid.hp <= 0 and not raid.killed_at:
        raid.hp = 0
        raid.killed_at = now()
        killed = True
        await _kill_rewards(db, raid, unit)
    return {"damage": dmg, "boss_hp": raid.hp, "boss_max_hp": raid.max_hp, "killed": killed, "free": used_free,
            "battle": {"units": res.units, "log": res.log, "rounds": res.rounds, "wiped": res.wiped},
            "reward": reward}


async def _kill_rewards(db: AsyncSession, raid: Raid, unit: str) -> None:
    cfg = data.economy()["raid"]
    uids = {r for (r,) in (await db.execute(select(RaidAttempt.user_id).where(RaidAttempt.raid_id == raid.id)))}
    for uid in uids:
        u = await db.get(User, uid)
        if u is None:
            continue
        await economy.add_resource(db, u, "crystals", cfg["kill_crystals"], "raid_kill", str(raid.id))
        types = [data.line(m.species)["type"] for m in await monsters.party(db, u)]
        cap_type = next((t for t in types if t in data.BASE_TYPES), "plastic")
        await monsters.grant_capsule(db, u, cap_type, "raid_kill")
    await region.change(db, unit, data.economy()["region"]["raid_kill_restore"], "raid_kill")


async def board(db: AsyncSession, raid: Raid, limit: int = 10) -> list[dict]:
    q = (select(RaidAttempt.user_id, func.sum(RaidAttempt.damage).label("dmg"), func.count().label("n"))
         .where(RaidAttempt.raid_id == raid.id).group_by(RaidAttempt.user_id)
         .order_by(func.sum(RaidAttempt.damage).desc()).limit(limit))
    out = []
    for uid, dmg, n in (await db.execute(q)).all():
        u = await db.get(User, uid)
        out.append({"nickname": u.nickname if u else "?", "damage": int(dmg), "attempts": int(n)})
    return out


def boss_view(key: str) -> dict:
    b = data.bosses()["bosses"][key]
    return {"key": key, "name": b["name"], "weak": b["weak"], "desc": b["desc"], "habit": b["habit"]}


_ = UserMonster
