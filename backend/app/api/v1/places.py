from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Place, Region, Zone
from app.services.game import actions, data

router = APIRouter()

KIND_NAMES = {"recycle_point": "재활용 분리배출장소", "clothes_bin": "의류수거함", "bag_shop": "종량제봉투 판매소",
              "battery_bin": "폐건전지·소형가전 수거함", "reverse_vending": "무인회수기", "other": "기타 수거함"}


def place_view(p: Place, dist: float | None = None) -> dict:
    return {"id": p.id, "kind": p.kind, "kind_name": KIND_NAMES.get(p.kind, p.kind), "name": p.name,
            "address": p.address, "detail": p.detail, "lat": p.lat, "lng": p.lng, "hours": p.hours,
            "items": p.items, "region_code": p.region_code, "is_active": p.is_active,
            "distance_m": round(dist) if dist is not None else None,
            "can_verify": p.kind in actions.DISPOSAL_KINDS and p.is_active}


@router.get("/places")
async def places(lat: float = Query(ge=33, le=39), lng: float = Query(ge=124, le=132),
                 radius: float = Query(1000, ge=50, le=5000), kind: str | None = None,
                 db: AsyncSession = Depends(get_db)):
    kinds = tuple(kind.split(",")) if kind else None
    rows = await actions.nearby_places(db, lat, lng, radius, kinds, limit=300)
    return [place_view(p, d) for p, d in rows]


MAP_MAX_AREA = 0.35      # 위도·경도 제곱도. 휴대폰 화면 기준 확대 10단계 정도까지
MAP_MAX_ROWS = 40000


@router.get("/places/map")
async def places_map(south: float = Query(ge=32, le=40), west: float = Query(ge=123, le=133),
                     north: float = Query(ge=32, le=40), east: float = Query(ge=123, le=133),
                     kind: str | None = None, db: AsyncSession = Depends(get_db)):
    """지도 화면 범위 안의 수거장 전부 (가벼운 형식: [id, 종류, 위도, 경도, 사용 중]).

    자세한 정보는 누를 때 /places/{id} 로 받는다.
    """
    if north <= south or east <= west:
        raise HTTPException(400, "지도 범위를 다시 확인해 주세요")
    if (north - south) * (east - west) > MAP_MAX_AREA:
        raise HTTPException(400, "지도를 조금 더 확대해 주세요")
    q = select(Place.id, Place.kind, Place.lat, Place.lng, Place.is_active).where(
        Place.lat.between(south, north), Place.lng.between(west, east))
    if kind:
        q = q.where(Place.kind.in_(kind.split(",")))
    rows = (await db.execute(q.limit(MAP_MAX_ROWS + 1))).all()
    return {"truncated": len(rows) > MAP_MAX_ROWS,
            "rows": [[i, k, round(la, 6), round(ln, 6), 1 if act else 0] for i, k, la, ln, act in rows[:MAP_MAX_ROWS]]}


SIDO_SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "대전광역시": "대전",
              "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "충청북도": "충북",
              "충청남도": "충남", "전북특별자치도": "전북", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
              "전남광주통합특별시": "전남광주"}
_CLUSTER_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CLUSTER_TTL = 600.0


async def _dong_clusters(db: AsyncSession, kinds: tuple[str, ...]) -> list[dict]:
    """행정동별 수거장 수와 수거장 위치 평균 (종류 조합마다 10분 캐시)."""
    import time
    key = ",".join(sorted(kinds))
    hit = _CLUSTER_CACHE.get(key)
    if hit and time.monotonic() - hit[0] < _CLUSTER_TTL:
        return hit[1]
    q = (select(Region.code, Region.name, Region.gu, Region.sido, Region.sigungu_code, func.count(),
                func.avg(Place.lat), func.avg(Place.lng))
         .join(Region, Region.code == Place.region_code).where(Place.is_active.is_(True)).group_by(Region.code))
    if kinds:
        q = q.where(Place.kind.in_(kinds))
    out = [{"code": c, "name": n, "gu": g, "sido": sd, "sgg": sg, "n": int(cnt), "lat": float(la), "lng": float(ln)}
           for c, n, g, sd, sg, cnt, la, ln in (await db.execute(q)).all()]
    _CLUSTER_CACHE[key] = (time.monotonic(), out)
    return out


@router.get("/places/clusters")
async def places_clusters(level: str = Query(pattern="^(sido|sigungu|dong)$"),
                          south: float = Query(ge=30, le=42), west: float = Query(ge=120, le=135),
                          north: float = Query(ge=30, le=42), east: float = Query(ge=120, le=135),
                          kind: str | None = None, db: AsyncSession = Depends(get_db)):
    """축소한 지도용: 지역(시·도 / 시·군·구 / 행정동)별로 묶은 수거장 수."""
    kinds = tuple(k for k in (kind or "").split(",") if k)
    dongs = await _dong_clusters(db, kinds)
    if level == "dong":
        groups = [{"key": d["code"], "name": d["name"], "n": d["n"], "lat": d["lat"], "lng": d["lng"]} for d in dongs]
    else:
        acc: dict[str, dict] = {}
        for d in dongs:
            if level == "sido":
                k, name = d["sido"], SIDO_SHORT.get(d["sido"], d["sido"])
            else:
                k, name = d["sgg"], d["gu"].split()[-1] if d["gu"] else d["sgg"]
            g = acc.setdefault(k, {"key": k, "name": name, "n": 0, "slat": 0.0, "slng": 0.0})
            g["n"] += d["n"]
            g["slat"] += d["lat"] * d["n"]
            g["slng"] += d["lng"] * d["n"]
        groups = [{"key": g["key"], "name": g["name"], "n": g["n"], "lat": g["slat"] / g["n"], "lng": g["slng"] / g["n"]}
                  for g in acc.values() if g["n"]]
    # 화면 밖이라도 가장자리에 걸친 묶음은 보이게 범위를 조금 넓혀 거른다
    mlat, mlng = (north - south) * 0.2, (east - west) * 0.2
    return [{**g, "lat": round(g["lat"], 5), "lng": round(g["lng"], 5)} for g in groups
            if south - mlat <= g["lat"] <= north + mlat and west - mlng <= g["lng"] <= east + mlng]


@router.get("/places/{place_id}")
async def place(place_id: int, db: AsyncSession = Depends(get_db)):
    p = await db.get(Place, place_id)
    if p is None:
        raise HTTPException(404, "수거장을 찾을 수 없어요")
    return place_view(p)


@router.get("/regions/sido")
async def sido_list(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Region.sido).distinct().order_by(Region.sido))).scalars()
    return [s for s in rows if s]


@router.get("/regions/sigungu")
async def sigungu_list(sido: str, db: AsyncSession = Depends(get_db)):
    q = (select(Region.sigungu_code, Region.gu).where(Region.sido == sido).distinct().order_by(Region.gu))
    return [{"code": c, "name": n} for c, n in (await db.execute(q)).all()]


@router.get("/regions/list")
async def regions_list(sigungu_code: str | None = None, sido: str | None = None, db: AsyncSession = Depends(get_db)):
    """행정동 목록. 시군구 또는 시도를 지정해야 한다 (전국 약 3,500개)."""
    if not sigungu_code and not sido:
        raise HTTPException(400, "시·도 또는 시·군·구를 골라 주세요")
    zones = {z.id: z.name for z in (await db.execute(select(Zone))).scalars()}
    q = select(Region).order_by(Region.gu, Region.name)
    q = q.where(Region.sigungu_code == sigungu_code) if sigungu_code else q.where(Region.sido == sido)
    return [{"code": r.code, "name": r.name, "gu": r.gu, "sido": r.sido, "sigungu_code": r.sigungu_code,
             "population": r.population, "zone": zones.get(r.zone_id), "center": [r.center_lat, r.center_lng],
             "dump_weekdays": r.dump_weekdays} for r in (await db.execute(q)).scalars()]


@router.get("/regions/{code}")
async def region_one(code: str, db: AsyncSession = Depends(get_db)):
    r = await db.get(Region, code)
    if r is None:
        raise HTTPException(404, "동네를 찾을 수 없어요")
    return {"code": r.code, "name": r.name, "gu": r.gu, "sido": r.sido, "sigungu_code": r.sigungu_code}


@router.get("/guides")
async def guides(q: str | None = None):
    g = data.guides()
    items = g["items"]
    if q:
        items = [it for it in items if q in it["name"] or q in g["categories"][it["category"]]["name"]]
    return {"categories": {k: {"name": v["name"], "type": v["type"]} for k, v in g["categories"].items()},
            "habits": {k: v["name"] for k, v in g["habits"].items()}, "items": items}
