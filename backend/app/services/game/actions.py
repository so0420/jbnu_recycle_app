"""핵심 행동: 스캔(집) → 가방, 배출 인증(수거장) → 가방 정산·보상."""
import math
from collections import Counter
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import BagItem, Capsule, ClassifyLog, Place, Region, User, Verification
from app.services import images
from app.services.ai.classifier import ClassifyResult
from app.services.clock import now
from app.services.game import data, economy, monsters, region

DISPOSAL_KINDS = ("recycle_point", "clothes_bin", "battery_bin", "reverse_vending")
SPECIAL_KIND_TYPE = {"battery_bin": "volt", "clothes_bin": "fabric"}


class VerifyFail(Exception):
    def __init__(self, code: str, message: str, detail: dict | None = None):
        self.code, self.message, self.detail = code, message, detail or {}


# ───────── 거리 ─────────
def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def nearby_places(db: AsyncSession, lat: float, lng: float, radius: float, kinds: tuple | None = None,
                        limit: int = 200) -> list[tuple[Place, float]]:
    dlat = radius / 111_000
    dlng = radius / (111_000 * max(0.2, math.cos(math.radians(lat))))
    q = select(Place).where(Place.lat.between(lat - dlat, lat + dlat), Place.lng.between(lng - dlng, lng + dlng))
    if kinds:
        q = q.where(Place.kind.in_(kinds))
    kx = math.cos(math.radians(lat))
    q = q.order_by(((Place.lat - lat) * (Place.lat - lat)) + ((Place.lng - lng) * kx) * ((Place.lng - lng) * kx)) \
         .limit(limit * 2)
    rows = [(p, haversine(lat, lng, p.lat, p.lng)) for p in (await db.execute(q)).scalars()]
    rows = [r for r in rows if r[1] <= radius]
    rows.sort(key=lambda r: r[1])
    return rows[:limit]


# ───────── 배출일 ─────────
def is_dump_time(r: Region | None, t: datetime) -> bool:
    """수거 전날 18:00 ~ 수거일 06:00 이면 배출 시간. 요일 정보가 없으면 항상 True."""
    if r is None or not r.dump_weekdays:
        return True
    days = {int(x) for x in r.dump_weekdays.split(",") if x.strip()}
    # 파이썬 weekday: 월=0 … 일=6 → 일=0 기준으로 변환
    def sun0(d: datetime) -> int:
        return (d.weekday() + 1) % 7
    if t.hour < 6 and sun0(t) in days:
        return True
    if t.hour >= 18 and sun0(t + timedelta(days=1)) in days:
        return True
    return False


def next_dump_window(r: Region | None, t: datetime) -> datetime | None:
    if r is None or not r.dump_weekdays:
        return None
    start = 0
    while start < 48 and is_dump_time(r, (t + timedelta(hours=start)).replace(minute=0, second=0, microsecond=0)):
        start += 1                       # 지금 배출 시간이면 이번 시간대가 끝난 뒤의 다음 시간대를 찾는다
    for h in range(start, 24 * 8):
        c = (t + timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
        if is_dump_time(r, c):
            return c
    return None


# ───────── 스캔 ─────────
async def on_scan(db: AsyncSession, user: User, res: ClassifyResult, log: ClassifyLog) -> dict:
    eco = data.economy()
    d = await economy.daily(db, user)
    out: dict = {"xp": 0, "bag": None, "habit": None, "dex_new": None, "duplicate": False}
    if res.category is None:
        return out
    # 같은 사진(또는 거의 같은 사진)은 보상 없음
    since = now() - timedelta(days=7)
    recent = (await db.execute(select(ClassifyLog.phash).where(
        ClassifyLog.user_id == user.id, ClassifyLog.id != log.id, ClassifyLog.created_at >= since,
        ClassifyLog.category.is_not(None), ClassifyLog.judged_by != "user"))).scalars()
    if any(images.hamming(log.phash, h) <= 6 for h in recent if h):
        out["duplicate"] = True
        return out
    d.scan_count += 1          # 미션은 새로 알아본 물건만 센다 (같은 사진·모르는 사진 제외)
    if d.guide_xp_count < eco["account_xp"]["scan_daily_cap"]:
        d.guide_xp_count += 1
        out["xp"] = (await economy.add_xp(db, user, eco["account_xp"]["scan"], "scan", str(log.id)))["xp"]
    if res.item_label and res.item_label in data.items_by_label():
        if await economy.add_dex(db, user, "item", res.item_label):
            out["dex_new"] = res.item_label
    type_ = data.category_type(res.category)
    if type_ == "none":
        return out
    # 가방
    cnt = await bag_count(db, user)
    if cnt < economy.bag_capacity(user):
        item = BagItem(user_id=user.id, category=res.category, item_label=res.item_label, type=type_,
                       is_clean=bool(res.clean), habit_ok=bool(res.habit_ok), classify_log_id=log.id)
        db.add(item)
        out["bag"] = {"added": True, "count": cnt + 1, "capacity": economy.bag_capacity(user)}
    else:
        out["bag"] = {"added": False, "count": cnt, "capacity": economy.bag_capacity(user)}
    # 습관 퀘스트
    if res.habit_ok and type_ in data.guides()["habits"]:
        out["habit"] = {"type": type_, "count": await economy.add_habit(db, user, type_)}
    return out


async def bag_items(db: AsyncSession, user: User) -> list[BagItem]:
    exp = now() - timedelta(days=data.economy()["verify"]["bag_expire_days"])
    q = select(BagItem).where(BagItem.user_id == user.id, BagItem.settled_verification_id.is_(None),
                              BagItem.created_at >= exp).order_by(BagItem.id)
    return list((await db.execute(q)).scalars())


async def bag_count(db: AsyncSession, user: User) -> int:
    return len(await bag_items(db, user))


# ───────── 배출 인증 ─────────
async def check_location(db: AsyncSession, lat: float, lng: float, accuracy: float) -> list[tuple[Place, float]]:
    """인증 가능한 반경 안의 수거장 목록 (가까운 순). 없으면 VerifyFail."""
    if accuracy > settings.VERIFY_MAX_ACCURACY_M:
        raise VerifyFail("LOW_ACCURACY", "위치가 정확하지 않아요. 잠시 뒤 다시 시도하거나 밖으로 나와 주세요",
                         {"accuracy": accuracy})
    limit = max(settings.VERIFY_RADIUS_M, min(accuracy, settings.VERIFY_MAX_ACCURACY_M))
    near = await nearby_places(db, lat, lng, max(limit, 300), DISPOSAL_KINDS, limit=5)
    near = [(p, dist) for p, dist in near if p.is_active]
    if not near or near[0][1] > limit:
        detail = {"nearest_m": round(near[0][1]) if near else None,
                  "nearest_name": (near[0][0].name or near[0][0].address) if near else None, "limit_m": round(limit)}
        raise VerifyFail("TOO_FAR", f"수거장에서 {round(limit)}m 안에서 인증해 주세요", detail)
    return [(p, dist) for p, dist in near if dist <= limit]


async def pick_place(db: AsyncSession, user: User, cands: list[tuple[Place, float]]) -> tuple[Place, float] | None:
    """같은 자리에 수거함이 여러 개면 오늘 아직 인증하지 않은 곳을 고른다 (특수 수거함 먼저)."""
    order = sorted(cands, key=lambda pd: (pd[0].kind not in SPECIAL_KIND_TYPE, pd[1]))
    for p, dist in order:
        if not await place_done_today(db, user, p):
            return p, dist
    return None


async def settle(db: AsyncSession, user: User, place: Place, v: Verification) -> dict:
    """인증 성공 후 보상 정산 (한 트랜잭션)."""
    eco = data.economy()
    d = await economy.daily(db, user)
    w = await economy.weekly(db, user)
    region_obj = await db.get(Region, place.region_code) if place.region_code else None
    home = await db.get(Region, user.region_code) if user.region_code else None

    out: dict = {"xp": 0, "xp_breakdown": [], "level_before": user.level}
    idx = d.verify_count
    d.verify_count += 1
    w.verify_count += 1
    rewarded = idx < eco["verify"]["daily_reward_cap"]

    # 첫 인증이면 내 동네 확정
    if user.region_confirmed_at is None and region_obj is not None:
        if user.region_code and user.region_code != region_obj.code:
            out["region_suggest"] = {"code": region_obj.code, "name": region_obj.name}
        user.region_code = user.region_code or region_obj.code
        user.region_confirmed_at = now()
        home = await db.get(Region, user.region_code)

    if rewarded:
        r = await economy.add_xp(db, user, eco["account_xp"]["verify"][idx], "verify", str(v.id))
        out["xp"] += r["xp"]
        out["xp_breakdown"].append({"type": "verify", "amount": r["xp"]})

    dump_time = is_dump_time(home, now())
    # 내 동네 = 같은 경쟁 단위(시군구·권역) 또는 인접 행정동
    in_home = bool(home and region_obj and (
        region_obj.code == home.code
        or region_obj.code in (home.neighbors or "").split(";")
        or (region.unit_of(region_obj) is not None and region.unit_of(region_obj) == region.unit_of(home))))
    out["dump_time"] = dump_time
    out["in_home_area"] = in_home

    # 가방 정산
    special = SPECIAL_KIND_TYPE.get(place.kind)
    items = [it for it in await bag_items(db, user)
             if it.type in data.BASE_TYPES or it.type == special]
    mats: Counter[str] = Counter()
    clean_n = 0
    if rewarded:
        for it in items:
            mats[it.type] += eco["verify"]["per_bag_item"]
            if it.is_clean:
                mats[it.type] += eco["verify"]["clean_bonus"]
                clean_n += 1
            it.settled_verification_id = v.id
            if it.type not in (w.types or []):
                w.types = [*(w.types or []), it.type]
        if special:
            mats[special] += eco["verify"]["special_materials"]
        type_counts = Counter(it.type for it in items if it.type in data.BASE_TYPES)
        base_type = type_counts.most_common(1)[0][0] if type_counts else "plastic"
        mats[base_type] += eco["verify"]["base_materials"]
        got = {}
        for mat, n in mats.items():
            got[mat] = await economy.add_resource(db, user, f"mat:{mat}", n, "verify", str(v.id))
        out["materials"] = got
        out["bag_settled"] = [{"category": it.category, "item_label": it.item_label, "type": it.type,
                               "clean": it.is_clean} for it in items]
        out["coins"] = await economy.add_resource(db, user, "coins", eco["verify"]["coins"], "verify", str(v.id))
        tickets = eco["verify"]["tickets"]
        # 캡슐
        cap_type = special or base_type
        bonus = eco["capsule"]["clean_bonus_rate"] if items and clean_n == len(items) else 0.0
        if special:
            granted = (await db.execute(select(Capsule.id).where(
                Capsule.user_id == user.id, Capsule.type == special).limit(1))).first()
            if granted is not None:
                cap_type = base_type
        cap = await monsters.grant_capsule(db, user, cap_type, "verify", bonus)
        out["capsule"] = {"id": cap.id, "type": cap.type}
    else:
        tickets = 0
        out["note"] = "오늘 보상은 3번까지예요. 인증 기록은 남았어요"

    # 배출일 보너스 (내 동·인접 동 수거장, 배출 시간, 하루 1번)
    if rewarded and in_home and dump_time and not d.dumpday_ticket:
        d.dumpday_ticket = True
        out["dumpday_bonus"] = True
        tickets += eco["verify"]["dumpday_ticket"]
        r = await economy.add_xp(db, user, eco["account_xp"]["dumpday_bonus"], "dumpday", str(v.id))
        out["xp"] += r["xp"]
        out["xp_breakdown"].append({"type": "dumpday", "amount": r["xp"]})
    if tickets:
        out["tickets"] = await economy.add_resource(db, user, "tickets", tickets, "verify", str(v.id))

    # 지역 청결도 (내 동네일 때, 하루 보상 상한 안에서만)
    if rewarded and in_home and home:
        unit = region.unit_of(home)
        if unit:
            out["region_restore"] = await region.on_verification(db, unit, user)
            out["region_cleanliness"] = round((await region.state(db, unit)).cleanliness)

    # 주간 목표
    goal = 3
    out["weekly"] = {"count": w.verify_count, "goal": goal}
    if w.verify_count == goal:
        r = await economy.add_xp(db, user, eco["account_xp"]["weekly_goal"], "weekly_goal", str(v.id))
        out["xp"] += r["xp"]
        out["xp_breakdown"].append({"type": "weekly_goal", "amount": r["xp"]})
        out["weekly"]["completed_now"] = True

    # 수거장 스탬프
    if await economy.add_dex(db, user, "stamp", str(place.id)):
        out["stamp_new"] = {"place_id": place.id}

    out["level_after"] = user.level
    out["evolution_ready"] = await _evolution_ready(db, user)
    return out


async def _evolution_ready(db: AsyncSession, user: User) -> list[dict]:
    hab = await economy.habits(db, user)
    mats = await economy.materials(db, user)
    ready = []
    for m in await monsters.list_owned(db, user):
        r = monsters.evolve_rule(m)
        if r and m.level >= r["level"] and hab.get(monsters.habit_type(m), 0) >= r["habits"]                 and mats.get(monsters.levelup_cost(m)["material"], 0) >= r["materials"]                 and user.crystals >= r["crystals"]:
            ready.append({"id": m.id, "name": data.line(m.species)["names"][m.stage - 1]})
    return ready


def suspicious_speed(user: User, lat: float, lng: float) -> str | None:
    if user.last_verified_at and user.last_lat is not None and user.last_lng is not None:
        hours = max((now() - user.last_verified_at).total_seconds() / 3600, 1 / 3600)
        kmh = haversine(user.last_lat, user.last_lng, lat, lng) / 1000 / hours
        if kmh > 150:
            return f"이동 속도 {kmh:.0f}km/h"
    return None


async def duplicate_photo(db: AsyncSession, user: User, place: Place, phash: str) -> bool:
    since = now() - timedelta(days=7)
    q = select(Verification.phash).where(
        Verification.created_at >= since, Verification.result == "success",
        (Verification.user_id == user.id) | (Verification.place_id == place.id))
    return any(h and images.hamming(phash, h) <= 6 for h in (await db.execute(q)).scalars())


async def place_done_today(db: AsyncSession, user: User, place: Place) -> bool:
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(Verification.id).where(Verification.user_id == user.id, Verification.place_id == place.id,
                                      Verification.result == "success", Verification.created_at >= start)
    return (await db.execute(q)).first() is not None


_ = HTTPException
