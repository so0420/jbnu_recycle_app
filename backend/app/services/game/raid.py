"""동네(시군구) 레이드: 주간 보스, 비동기 협동 체력 깎기, 처치 보상."""
import random
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassifyLog, Raid, RaidAttempt, Region, User, Verification
from app.services.clock import now, week_start
from app.services.game import battle, data, economy, monsters, region
from app.utils.log import logger

ATTEMPTS_PER_USER = 7             # 3.5일 × 하루 2회 → 보통 참여율이면 3~4일 안에 처치
MIN_HP = 3000
LONE_STARTER_DAMAGE = 150         # 파티를 못 꾸린 사용자의 1회 예상 피해 (Lv1 스타터 수준)


def boss_of_week(ws=None) -> str:
    ws = ws or week_start()
    order = data.bosses()["order"]
    return order[(ws.toordinal() // 7) % len(order)]


def next_boss() -> str:
    return boss_of_week(week_start() + timedelta(days=7))


async def _raid_ready_users(db: AsyncSession, unit: str) -> list[User]:
    """이 단위에서 레이드에 참여할 수 있고(정원 레벨) 최근 7일에 활동한 사용자 (쿼리 한 번)."""
    us = await region.units(db)
    codes = us.get(unit, {}).get("regions", [])
    if not codes:
        return []
    since = now() - timedelta(days=7)
    need = data.economy()["garden"]["raid"]
    active = exists().where(Verification.user_id == User.id, Verification.created_at >= since) | \
        exists().where(ClassifyLog.user_id == User.id, ClassifyLog.created_at >= since)
    q = select(User).where(User.region_code.in_(codes), User.deleted_at.is_(None), User.level >= need, active)
    return list((await db.execute(q)).scalars())


async def party_units(db: AsyncSession, user: User) -> list[battle.Unit]:
    ms = await monsters.party(db, user)
    return [battle.make_ally(f"a{m.id}", monsters.view(m), m.slot == 0) for m in ms]


async def estimate_damage(db: AsyncSession, user: User, boss: str) -> float:
    views = [(f"a{m.id}", monsters.view(m), m.slot == 0) for m in await monsters.party(db, user)]
    if not views:
        return LONE_STARTER_DAMAGE
    total = 0
    for seed in range(3):
        party = [battle.make_ally(uid, v, front) for uid, v, front in views]   # 전투가 유닛을 바꾸므로 매번 새로
        total += battle.simulate(party, boss, 1e12, seed).damage
    return total / 3


async def current(db: AsyncSession, unit: str) -> Raid:
    ws = week_start()
    raid = (await db.execute(select(Raid).where(Raid.unit == unit, Raid.week_start == ws))).scalars().first()
    if raid:
        return raid
    boss = boss_of_week(ws)
    est = 0.0
    for u in await _raid_ready_users(db, unit):
        est += await estimate_damage(db, u, boss)
    hp = int(max(MIN_HP, est * ATTEMPTS_PER_USER))
    from sqlalchemy.dialects.mysql import insert as mysql_insert
    await db.execute(mysql_insert(Raid).values(unit=unit, boss=boss, week_start=ws, max_hp=hp, hp=hp)
                     .prefix_with("IGNORE"))
    return (await db.execute(select(Raid).where(Raid.unit == unit, Raid.week_start == ws)
                             .execution_options(populate_existing=True))).scalars().one()


async def user_unit(db: AsyncSession, user: User) -> str:
    if not user.region_code:
        raise HTTPException(400, "내 동네를 먼저 정해 주세요")
    r = await db.get(Region, user.region_code)
    unit = region.unit_of(r)
    if not unit:
        raise HTTPException(400, "내 동네가 레이드 지역에 속하지 않아요")
    return unit


async def attempt(db: AsyncSession, user: User) -> dict:
    economy.require(user, "raid")
    if user.region_confirmed_at is None:
        raise HTTPException(400, "첫 배출 인증으로 내 동네가 확정되면 레이드에 참여할 수 있어요")
    unit = await user_unit(db, user)
    raid = await current(db, unit)
    await db.flush()
    # 보스 행을 잠그고 최신 체력·처치 여부를 다시 읽는다 (동시 도전 시 피해 누락·보상 중복 방지)
    raid = (await db.execute(select(Raid).where(Raid.id == raid.id).with_for_update()
                             .execution_options(populate_existing=True))).scalars().one()
    if raid.killed_at:
        raise HTTPException(400, "이번 주 보스는 이미 쓰러졌어요. 다음 주 보스를 기다려 주세요")
    party_ms = await monsters.party(db, user)
    party = [battle.make_ally(f"a{m.id}", monsters.view(m), m.slot == 0) for m in party_ms]
    if not party:
        raise HTTPException(400, "파티에 리몬을 넣어 주세요")
    d = await economy.daily(db, user)
    used_free = False
    if not d.free_raid_used:
        d.free_raid_used = True
        used_free = True
    else:
        await economy.add_resource(db, user, "tickets", -1, "raid", str(raid.id))

    seed = random.randrange(1, 2 ** 31)
    res = battle.simulate(party, raid.boss, float(raid.hp), seed, boss_hp_ratio=raid.hp / raid.max_hp)
    dmg = min(res.damage, raid.hp)
    raid.hp -= dmg
    db.add(RaidAttempt(raid_id=raid.id, user_id=user.id, damage=dmg, seed=seed,
                       log_json={"units": res.units, "log": res.log}))
    await db.flush()      # 마지막 일격을 넣은 사람도 처치 보상 대상에 들어가게
    d.raid_count += 1
    cfg = data.economy()["raid"]
    reward = {
        "coins": await economy.add_resource(db, user, "coins", cfg["reward_coins_per_attempt"], "raid", str(raid.id)),
        "materials": {},
    }
    # 재료는 도전 1회에 한 번 (앞줄 리몬의 타입)
    front = next((m for m in party_ms if m.slot == 0), party_ms[0])
    t = data.line(front.species)["type"]
    if t in data.MATERIALS:
        reward["materials"][t] = await economy.add_resource(db, user, f"mat:{t}", cfg["reward_materials_per_attempt"],
                                                            "raid", str(raid.id))
    if d.raid_count == 1:
        reward["xp"] = (await economy.add_xp(db, user, data.economy()["account_xp"]["raid_daily"], "raid"))["xp"]
    killed = False
    if raid.hp <= 0 and not raid.killed_at:
        raid.hp = 0
        raid.killed_at = now()
        killed = True          # 보상은 이 트랜잭션이 커밋된 뒤 pay_kill_rewards 로 따로 지급
    return {"raid_id": raid.id, "damage": dmg, "boss_hp": raid.hp, "boss_max_hp": raid.max_hp, "killed": killed,
            "free": used_free,
            "battle": {"units": res.units, "log": res.log, "rounds": res.rounds, "wiped": res.wiped},
            "reward": reward}


async def _claim(db: AsyncSession, name: str, key: str) -> bool:
    from sqlalchemy.dialects.mysql import insert as mysql_insert
    from app.models import JobLog
    res = await db.execute(mysql_insert(JobLog).values(name=name, key=key).prefix_with("IGNORE"))
    return res.rowcount == 1


async def pay_kill_rewards(raid_id: int) -> None:
    """처치 보상: 공격 트랜잭션과 따로, 참여자마다 짧은 트랜잭션으로 한 번씩만 지급한다.

    지급 기록은 (레이드, 사용자)마다 남기므로 중간에 실패해도 다음 실행(스케줄러)에서 나머지를 이어서 준다.
    """
    from sqlalchemy import update as sa_update
    from app.database.session import AsyncSessionLocal
    from app.models import EconomyEvent
    cfg = data.economy()["raid"]
    async with AsyncSessionLocal() as db:
        raid = await db.get(Raid, raid_id)
        if raid is None or raid.killed_at is None:
            return
        uids = sorted({r for (r,) in (await db.execute(
            select(RaidAttempt.user_id).where(RaidAttempt.raid_id == raid_id)))})
        unit = raid.unit
    all_ok = True
    for uid in uids:
        try:
            async with AsyncSessionLocal() as db:
                u = (await db.execute(select(User).where(User.id == uid).with_for_update()
                                      .execution_options(populate_existing=True))).scalars().one_or_none()
                if u is None or u.deleted_at is not None:
                    await db.rollback()
                    continue
                if not await _claim(db, "raid_kill", f"{raid_id}:{uid}"):
                    await db.rollback()          # 이미 받음
                    continue
                await db.execute(sa_update(User).where(User.id == uid)
                                 .values(crystals=User.crystals + cfg["kill_crystals"]))
                db.add(EconomyEvent(user_id=uid, resource="crystals", delta=cfg["kill_crystals"], reason="raid_kill",
                                    ref=str(raid_id)))
                types = [data.line(m.species)["type"] for m in await monsters.party(db, u)]
                cap_type = next((t for t in types if t in data.BASE_TYPES), "plastic")
                await monsters.grant_capsule(db, u, cap_type, "raid_kill")
                await db.commit()
        except Exception as e:   # 한 사람이 실패해도 나머지는 계속, 실패분은 다음 실행에서 다시
            all_ok = False
            logger.error(f"레이드 처치 보상 실패 raid={raid_id} user={uid}: {e!r}")
    try:
        async with AsyncSessionLocal() as db:
            if await _claim(db, "raid_kill_rg", str(raid_id)):
                await region.change(db, unit, data.economy()["region"]["raid_kill_restore"], "raid_kill")
            if all_ok:
                await _claim(db, "raid_kill_done", str(raid_id))
            await db.commit()
    except Exception as e:
        logger.error(f"레이드 처치 지역 회복 실패 raid={raid_id}: {e!r}")


async def retry_pending_kills() -> None:
    """처치됐지만 보상 지급이 끝나지 않은 레이드를 다시 처리 (스케줄러가 주기적으로 호출)."""
    from app.database.session import AsyncSessionLocal
    from app.models import JobLog
    async with AsyncSessionLocal() as db:
        ids = list((await db.execute(select(Raid.id).where(
            Raid.killed_at.is_not(None), Raid.killed_at >= now() - timedelta(days=14)))).scalars())
        done = set((await db.execute(select(JobLog.key).where(JobLog.name == "raid_kill_done"))).scalars())
    for rid in ids:
        if str(rid) not in done:
            await pay_kill_rewards(rid)


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
