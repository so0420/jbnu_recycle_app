"""지역 청결도 (게임시스템.md 5·8장). 단위 = 행정동 또는 권역(REGION_MODE)."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Region, RegionEvent, RegionState, User, Verification, Zone
from app.services.clock import now, today, week_start
from app.services.game import data


def cfg() -> dict:
    return data.economy()["region"]


def unit_of(region: Region | None) -> str | None:
    if region is None:
        return None
    if settings.REGION_MODE == "zone":
        return f"Z{region.zone_id}" if region.zone_id else None
    return region.code


async def units(db: AsyncSession) -> dict[str, dict]:
    """단위 id → {name, population, regions[]}"""
    regions = list((await db.execute(select(Region))).scalars())
    out: dict[str, dict] = {}
    if settings.REGION_MODE == "zone":
        zones = {z.id: z.name for z in (await db.execute(select(Zone))).scalars()}
        for r in regions:
            if not r.zone_id:
                continue
            u = out.setdefault(f"Z{r.zone_id}", {"name": zones.get(r.zone_id, "권역"), "population": 0,
                                                 "regions": []})
            u["population"] += r.population or 0
            u["regions"].append(r.code)
    else:
        for r in regions:
            out[r.code] = {"name": r.name, "population": r.population or 0, "regions": [r.code]}
    return out


async def weight(db: AsyncSession, unit: str) -> float:
    us = await units(db)
    pops = [u["population"] for u in us.values() if u["population"]]
    if not pops or not us.get(unit, {}).get("population"):
        return 1.0
    w = (sum(pops) / len(pops)) / us[unit]["population"]
    return max(cfg()["w_min"], min(cfg()["w_max"], w))


async def state(db: AsyncSession, unit: str) -> RegionState:
    ws = week_start()
    row = await db.get(RegionState, (ws, unit))
    if row is None:
        row = RegionState(week_start=ws, unit=unit, cleanliness=float(cfg()["start"]), verifs=0)
        db.add(row)
        await db.flush()
    return row


async def r_base(db: AsyncSession) -> float:
    n = max(1, len(await units(db)))
    since = now() - timedelta(days=7)
    cnt = (await db.execute(select(func.count()).select_from(Verification).where(
        Verification.result == "success", Verification.created_at >= since))).scalar_one()
    avg = cnt / 7
    return cfg()["target_restore"] * n / max(avg, n)


def clamp(v: float) -> float:
    return max(cfg()["min"], min(cfg()["max"], v))


async def change(db: AsyncSession, unit: str, amount: float, type_: str, user: User | None = None) -> RegionState:
    st = await state(db, unit)
    st.cleanliness = clamp(st.cleanliness + amount)
    db.add(RegionEvent(unit=unit, type=type_, amount=round(amount, 1), user_id=user.id if user else None,
                       nickname=user.nickname if user else None))
    return st


async def on_verification(db: AsyncSession, unit: str, user: User) -> float:
    st = await state(db, unit)
    boost = cfg()["crisis_restore"] if st.cleanliness < cfg()["crisis_below"] else 1.0
    amount = await r_base(db) * await weight(db, unit) * boost
    st.verifs += 1
    await change(db, unit, amount, "restore", user)
    return round(amount, 1)


async def daily_decay(db: AsyncSession) -> None:
    for unit in await units(db):
        await change(db, unit, -cfg()["daily_decay"], "decay")


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


async def standings(db: AsyncSession) -> list[dict]:
    us = await units(db)
    rows = []
    for unit, info in us.items():
        st = await state(db, unit)
        rows.append({"unit": unit, "name": info["name"], "cleanliness": round(st.cleanliness),
                     "verifs": st.verifs, "stage": stage_of(st.cleanliness), "regions": info["regions"]})
    rows.sort(key=lambda r: (-r["cleanliness"], -r["verifs"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


async def feed(db: AsyncSession, unit: str, limit: int = 20) -> list[dict]:
    q = (select(RegionEvent).where(RegionEvent.unit == unit, RegionEvent.type != "decay")
         .order_by(RegionEvent.id.desc()).limit(limit))
    return [{"type": e.type, "amount": e.amount, "nickname": e.nickname, "at": e.created_at.isoformat()}
            for e in (await db.execute(q)).scalars()]


def _unused() -> None:  # today 는 다른 모듈에서 재노출용
    _ = today
