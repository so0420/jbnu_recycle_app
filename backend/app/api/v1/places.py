from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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
