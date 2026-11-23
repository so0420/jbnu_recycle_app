"""지역 공방전 (발표 자료의 '지역 공방전').

- 공격권: 배출 시간에 우리 동네 수거장에서 인증하면 1장 (actions.settle). 레이드용 도전권과 따로 센다.
- 공격: 공격권 1장으로 이번 주에 참여한 다른 지역에 쓰레기를 던져 청결도를 깎는다.
- 방어: 그 지역 주민이 분리배출(인증)을 하면 청결도가 회복된다 (region.on_verification).
- 정화: 공격권 1장을 우리 지역에 써서 청결도를 회복한다 (공격 1회와 같은 크기, 위기 지역이면 더 크게).

피해 = 기준 회복량(r_base) × mult × 공격한 사람 지역의 인구 보정
       × 역전 보너스(우리보다 순위가 높은 지역) × 피로(오늘 많이 맞은 지역) × 위기 보호(위기 지역)
"""
from datetime import datetime, time as dtime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Region, RegionEvent, RegionState, User
from app.services.clock import today, week_start
from app.services.game import data, economy, monsters, region


def cfg() -> dict:
    return data.economy()["attack"]


def _day_start() -> datetime:
    return datetime.combine(today(), dtime.min)


async def home_unit(db: AsyncSession, user: User) -> str:
    if not user.region_code:
        raise HTTPException(400, "내 동네를 먼저 정해 주세요")
    unit = region.unit_of(await db.get(Region, user.region_code))
    if not unit:
        raise HTTPException(400, "내 동네가 공방전 지역에 속하지 않아요")
    return unit


async def attack_weight(db: AsyncSession, unit: str) -> float:
    c = cfg()
    return max(c["w_min"], min(c["w_max"], await region.raw_weight(db, unit)))


async def base_damage(db: AsyncSession, my_unit: str) -> float:
    return cfg()["mult"] * await region.r_base(db) * await attack_weight(db, my_unit)


def modifiers(base: float, my_rank: int | None, target_rank: int | None, hit_today: float,
              cleanliness: float) -> tuple[float, list[str]]:
    """기본 피해에 보정을 곱한다. (피해, 적용된 보정 목록)"""
    c, rc = cfg(), region.cfg()
    dmg, mods = base, []
    if target_rank is not None and (my_rank is None or target_rank < my_rank):
        dmg *= c["underdog"]
        mods.append("underdog")
    if hit_today > c["fatigue_after"]:
        dmg *= c["fatigue_mult"]
        mods.append("fatigue")
    if cleanliness < rc["crisis_below"]:
        dmg *= c["crisis_damage"]
        mods.append("crisis")
    return round(dmg, 1), mods


async def cleanse_amount(db: AsyncSession, my_unit: str, cleanliness: float) -> tuple[float, list[str]]:
    """정화 1회 회복량. (회복량, 적용된 보정 목록)"""
    rc = region.cfg()
    amount = cfg()["cleanse_mult"] * await region.r_base(db) * await attack_weight(db, my_unit)
    mods = []
    if cleanliness < rc["crisis_below"]:
        amount *= rc["crisis_restore"]
        mods.append("crisis_boost")
    return round(amount, 1), mods


async def _hits_today(db: AsyncSession, unit: str | None = None) -> dict[str, float]:
    """지역별 오늘 받은 공격 피해 합."""
    q = (select(RegionEvent.unit, func.coalesce(func.sum(-RegionEvent.amount), 0))
         .where(RegionEvent.type == "attack", RegionEvent.created_at >= _day_start()).group_by(RegionEvent.unit))
    if unit:
        q = q.where(RegionEvent.unit == unit)
    return {u: float(v) for u, v in (await db.execute(q)).all()}


async def _my_today(db: AsyncSession, user: User, unit: str | None = None) -> dict[str, int]:
    """오늘 내가 지역별로 공격한 횟수."""
    q = (select(RegionEvent.unit, func.count())
         .where(RegionEvent.type == "attack", RegionEvent.user_id == user.id,
                RegionEvent.created_at >= _day_start()).group_by(RegionEvent.unit))
    if unit:
        q = q.where(RegionEvent.unit == unit)
    return {u: int(n) for u, n in (await db.execute(q)).all()}


async def thrower(db: AsyncSession, user: User) -> dict | None:
    """쓰레기를 던지는 연출에 쓸 리몬 (파티 앞줄, 없으면 아무나)."""
    party = await monsters.party(db, user)
    m = next((m for m in party if m.slot == 0), party[0] if party else None)
    if m is None:
        owned = await monsters.list_owned(db, user)
        m = owned[0] if owned else None
    return monsters.view(m) if m else None


async def overview(db: AsyncSession, user: User) -> dict:
    mine = await home_unit(db, user)
    us = await region.units(db)
    rows, states = await region.ranked(db)
    ranks = {r["unit"]: r["rank"] for r in rows}
    hits = await _hits_today(db)
    my_today = await _my_today(db, user)
    base = await base_damage(db, mine)
    c = cfg()
    st = states.get(mine)
    clean = st.cleanliness if st else float(region.cfg()["start"])
    targets = []
    for r in rows:
        if r["unit"] == mine:
            continue
        dmg, mods = modifiers(base, ranks.get(mine), r["rank"], hits.get(r["unit"], 0.0), r["cleanliness"])
        used = my_today.get(r["unit"], 0)
        targets.append({**r, "damage": dmg, "mods": mods, "hit_today": round(hits.get(r["unit"], 0.0)),
                        "my_today": used, "can": used < c["daily_per_target"]})
    heal, heal_mods = await cleanse_amount(db, mine, clean)
    return {
        "unit": mine, "name": us.get(mine, {}).get("name"), "sido": us.get(mine, {}).get("sido"),
        "cleanse": {"amount": heal, "mods": heal_mods, "can": clean < region.cfg()["max"]},
        "mode": settings.REGION_MODE,
        "mine": {"cleanliness": round(clean), "stage": region.stage_of(clean), "rank": ranks.get(mine),
                 "verifs": st.verifs if st else 0, "hit_today": round(hits.get(mine, 0.0))},
        "confirmed": user.region_confirmed_at is not None,
        "attack_tickets": user.attack_tickets or 0, "cap": c["cap"], "daily_per_target": c["daily_per_target"],
        "total": len(rows), "targets": targets, "thrower": await thrower(db, user),
    }


async def cleanse(db: AsyncSession, user: User) -> dict:
    """정화 1회: 공격권 1장으로 우리 지역 청결도를 회복한다. 호출 전에 사용자 행을 잠가야 한다."""
    if user.region_confirmed_at is None:
        raise HTTPException(400, "첫 배출 인증으로 내 동네가 확정되면 정화할 수 있어요")
    mine = await home_unit(db, user)
    if (user.attack_tickets or 0) < 1:
        raise HTTPException(400, "공격권이 없어요. 배출 시간에 우리 동네 수거장에서 인증하면 받을 수 있어요")
    st = await region.state(db, mine)
    before = st.cleanliness
    if before >= region.cfg()["max"]:
        raise HTTPException(400, "우리 동네는 이미 가장 깨끗해요")
    amount, mods = await cleanse_amount(db, mine, before)
    await economy.add_resource(db, user, "attack_tickets", -1, "cleanse", mine)
    after = (await region.change(db, mine, amount, "cleanse", user)).cleanliness
    us = await region.units(db)
    return {
        "target": {"unit": mine, "name": us.get(mine, {}).get("name"), "sido": us.get(mine, {}).get("sido"),
                   "before": round(before, 1), "after": round(after, 1), "stage": region.stage_of(after)},
        "amount": round(after - before, 1), "planned": amount, "mods": mods,
        "attack_tickets": user.attack_tickets,
    }


async def attack(db: AsyncSession, user: User, target: str) -> dict:
    """공격 1회. 호출 전에 사용자 행을 잠가야 한다(locks.lock_user)."""
    c = cfg()
    if user.region_confirmed_at is None:
        raise HTTPException(400, "첫 배출 인증으로 내 동네가 확정되면 공격할 수 있어요")
    mine = await home_unit(db, user)
    if target == mine:
        raise HTTPException(400, "우리 동네는 공격할 수 없어요")
    us = await region.units(db)
    if target not in us:
        raise HTTPException(404, "지역을 찾을 수 없어요")
    st = await db.get(RegionState, (week_start(), target), populate_existing=True)
    if st is None or st.verifs == 0:
        raise HTTPException(400, "이번 주에 분리배출을 한 지역만 공격할 수 있어요")
    if (user.attack_tickets or 0) < 1:
        raise HTTPException(400, "공격권이 없어요. 배출 시간에 우리 동네 수거장에서 인증하면 받을 수 있어요")
    if (await _my_today(db, user, target)).get(target, 0) >= c["daily_per_target"]:
        raise HTTPException(400, f"같은 지역은 하루에 {c['daily_per_target']}번까지 공격할 수 있어요")

    rows, _ = await region.ranked(db)
    ranks = {r["unit"]: r["rank"] for r in rows}
    hit_today = (await _hits_today(db, target)).get(target, 0.0)
    before = st.cleanliness
    dmg, mods = modifiers(await base_damage(db, mine), ranks.get(mine), ranks.get(target), hit_today, before)
    await economy.add_resource(db, user, "attack_tickets", -1, "attack", target)
    after_st = await region.change(db, target, -dmg, "attack", user, src_unit=mine)
    after = after_st.cleanliness
    return {
        "target": {"unit": target, "name": us[target]["name"], "sido": us[target]["sido"],
                   "before": round(before, 1), "after": round(after, 1), "stage": region.stage_of(after),
                   "rank_before": ranks.get(target)},
        "from": {"unit": mine, "name": us.get(mine, {}).get("name")},
        "damage": round(before - after, 1), "planned": dmg, "mods": mods,
        "attack_tickets": user.attack_tickets,
    }
