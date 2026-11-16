"""지역 청결도 (게임시스템.md 5·8장).

경쟁 단위(REGION_MODE)
- sigungu: 전국 시·군·구 (기본, 약 250개)
- zone:    전주 시연용 권역 6개
- dong:    행정동
"""
import time
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Region, RegionEvent, RegionState, User, Verification, Zone
from app.services.clock import now, week_start
from app.services.game import data

_UNITS_CACHE: tuple[float, dict[str, dict]] | None = None
_UNITS_TTL = 600.0


def cfg() -> dict:
    return data.economy()["region"]


def unit_of(region: Region | None) -> str | None:
    if region is None:
        return None
    if settings.REGION_MODE == "zone":
        return f"Z{region.zone_id}" if region.zone_id else None
    if settings.REGION_MODE == "sigungu":
        return f"S{region.sigungu_code}" if region.sigungu_code else None
    return region.code


async def units(db: AsyncSession) -> dict[str, dict]:
    """단위 id → {name, sido, population, regions[]} (10분 캐시)"""
    global _UNITS_CACHE
    if _UNITS_CACHE and time.monotonic() - _UNITS_CACHE[0] < _UNITS_TTL:
        return _UNITS_CACHE[1]
    rows = (await db.execute(select(Region.code, Region.name, Region.gu, Region.sido, Region.sigungu_code,
                                    Region.zone_id, Region.population))).all()
    out: dict[str, dict] = {}
    if settings.REGION_MODE == "zone":
        zones = {z.id: z.name for z in (await db.execute(select(Zone))).scalars()}
        for code, name, gu, sido, sgg, zid, pop in rows:
            if not zid:
                continue
            u = out.setdefault(f"Z{zid}", {"name": zones.get(zid, "권역"), "sido": sido, "population": 0,
                                           "regions": []})
            u["population"] += pop or 0
            u["regions"].append(code)
    elif settings.REGION_MODE == "sigungu":
        for code, name, gu, sido, sgg, zid, pop in rows:
            if not sgg:
                continue
            u = out.setdefault(f"S{sgg}", {"name": gu, "sido": sido, "population": 0, "regions": []})
            u["population"] += pop or 0
            u["regions"].append(code)
    else:
        for code, name, gu, sido, sgg, zid, pop in rows:
            out[code] = {"name": f"{gu} {name}", "sido": sido, "population": pop or 0, "regions": [code]}
    _UNITS_CACHE = (time.monotonic(), out)
    return out


def invalidate_units() -> None:
    global _UNITS_CACHE
    _UNITS_CACHE = None


async def weight(db: AsyncSession, unit: str) -> float:
    us = await units(db)
    pops = [u["population"] for u in us.values() if u["population"]]
    if not pops or not us.get(unit, {}).get("population"):
        return 1.0
    w = (sum(pops) / len(pops)) / us[unit]["population"]
    return max(cfg()["w_min"], min(cfg()["w_max"], w))


async def state(db: AsyncSession, unit: str) -> RegionState:
    ws = week_start()
    from app.services.game.economy import ensure_row
    return await ensure_row(db, RegionState, (ws, unit), week_start=ws, unit=unit,
                            cleanliness=float(cfg()["start"]), verifs=0)


async def active_unit_count(db: AsyncSession) -> int:
    """이번 주 실제로 움직임이 있는 단위 수 (자동 스케일 기준)."""
    n = (await db.execute(select(func.count()).select_from(RegionState).where(
        RegionState.week_start == week_start(), RegionState.verifs > 0))).scalar_one()
    return max(1, n)


async def r_base(db: AsyncSession) -> float:
    n = await active_unit_count(db)
    since = now() - timedelta(days=7)
    cnt = (await db.execute(select(func.count()).select_from(Verification).where(
        Verification.result == "success", Verification.created_at >= since))).scalar_one()
    avg = cnt / 7
    return cfg()["target_restore"] * n / max(avg, n)


def clamp(v: float) -> float:
    return max(cfg()["min"], min(cfg()["max"], v))


async def change(db: AsyncSession, unit: str, amount: float, type_: str, user: User | None = None) -> RegionState:
    st = await state(db, unit)
    c = cfg()
    await db.execute(update(RegionState).where(RegionState.week_start == st.week_start, RegionState.unit == unit)
                     .values(cleanliness=func.least(c["max"], func.greatest(c["min"], RegionState.cleanliness + amount))))
    st = await db.get(RegionState, (st.week_start, unit), populate_existing=True)
    db.add(RegionEvent(unit=unit, type=type_, amount=round(amount, 1), user_id=user.id if user else None,
                       nickname=user.nickname if user else None))
    return st


async def on_verification(db: AsyncSession, unit: str, user: User) -> float:
    st = await state(db, unit)
    boost = cfg()["crisis_restore"] if st.cleanliness < cfg()["crisis_below"] else 1.0
    amount = await r_base(db) * await weight(db, unit) * boost
    await db.execute(update(RegionState).where(RegionState.week_start == st.week_start, RegionState.unit == unit)
                     .values(verifs=RegionState.verifs + 1))
    await change(db, unit, amount, "restore", user)
    return round(amount, 1)


async def daily_decay(db: AsyncSession) -> None:
    """이번 주 상태가 있는 단위만 감소 (참여자가 없는 단위는 시작값으로 표시)."""
    c = cfg()
    await db.execute(update(RegionState).where(RegionState.week_start == week_start())
                     .values(cleanliness=func.greatest(c["min"], RegionState.cleanliness - c["daily_decay"])))


def stage_of(c: float) -> dict:
    if c >= 900:
        return {"key": "sparkle", "name": "반짝반짝"}
    if c >= 700:
        return {"key": "clean", "name": "깨끗"}
    if c >= 400:
        return {"key": "normal", "name": "보통"}
    if c >= 200:
        return {"key": "dirty", "name": "더러움"}
    return {"key": "crisis", "name": "위기"}


async def standings(db: AsyncSession, mine: str | None = None, top: int = 30) -> dict:
    """참여한 단위만 순위에 올린다. 내 단위는 순위 밖이어도 따로 돌려준다."""
    us = await units(db)
    states = {s.unit: s for s in (await db.execute(
        select(RegionState).where(RegionState.week_start == week_start()))).scalars()}
    rows = []
    for unit, st in states.items():
        if unit not in us or st.verifs == 0:
            continue
        info = us[unit]
        rows.append({"unit": unit, "name": info["name"], "sido": info["sido"], "cleanliness": round(st.cleanliness),
                     "verifs": st.verifs, "stage": stage_of(st.cleanliness)})
    rows.sort(key=lambda r: (-r["cleanliness"], -r["verifs"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    me = next((r for r in rows if r["unit"] == mine), None)
    if mine and me is None and mine in us:
        st = states.get(mine)
        c = st.cleanliness if st else float(cfg()["start"])
        me = {"unit": mine, "name": us[mine]["name"], "sido": us[mine]["sido"], "cleanliness": round(c),
              "verifs": st.verifs if st else 0, "stage": stage_of(c), "rank": None}
    return {"mode": settings.REGION_MODE, "total": len(rows), "rows": rows[:top], "mine": me}


async def feed(db: AsyncSession, unit: str, limit: int = 20) -> list[dict]:
    q = (select(RegionEvent).where(RegionEvent.unit == unit, RegionEvent.type != "decay")
         .order_by(RegionEvent.id.desc()).limit(limit))
    return [{"type": e.type, "amount": e.amount, "nickname": e.nickname, "at": e.created_at.isoformat()}
            for e in (await db.execute(q)).scalars()]
