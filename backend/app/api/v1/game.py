from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.database import get_db
from app.models import Capsule, User
from app.services.game import actions, data, economy, missions, monsters

router = APIRouter()


async def _monsters_payload(db: AsyncSession, user: User) -> list[dict]:
    hab = await economy.habits(db, user)
    return [monsters.view(m, hab) for m in await monsters.list_owned(db, user)]


@router.get("/monsters")
async def list_monsters(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    out = {"monsters": await _monsters_payload(db, user), "habits": await economy.habits(db, user),
           "habit_names": {k: v["name"] for k, v in data.guides()["habits"].items()},
           "starters": [{"species": s, "name": data.line(s)["names"][0], "type": data.line(s)["type"],
                         "role": data.line(s)["role"], "desc": data.line(s)["desc"], "art": f"{s}_1"}
                        for s in data.species()["starters"]],
           "type_beats": data.species()["type_beats"]}
    await db.commit()
    return out


class StarterIn(BaseModel):
    species: str


@router.post("/monsters/starter")
async def starter(body: StarterIn, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    m = await monsters.choose_starter(db, user, body.species)
    await db.commit()
    return monsters.view(m)


@router.post("/monsters/{mid}/levelup")
async def levelup(mid: int, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    m = await monsters.get_owned(db, user, mid)
    await monsters.level_up(db, user, m)
    await db.commit()
    return monsters.view(m, await economy.habits(db, user))


@router.post("/monsters/{mid}/evolve")
async def evolve(mid: int, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    m = await monsters.get_owned(db, user, mid)
    r = await monsters.evolve(db, user, m)
    await db.commit()
    return {"evolved": r, "monster": monsters.view(m, await economy.habits(db, user))}


class PartyIn(BaseModel):
    ids: list[int | None]
    timings: dict[int, str] = {}


@router.put("/party")
async def set_party(body: PartyIn, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    await monsters.set_party(db, user, body.ids, body.timings)
    await db.commit()
    return {"monsters": await _monsters_payload(db, user)}


@router.post("/monsters/{mid}/expedition")
async def expedition(mid: int, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    m = await monsters.get_owned(db, user, mid)
    r = await monsters.send_expedition(db, user, m)
    await db.commit()
    return r


@router.post("/monsters/{mid}/expedition/claim")
async def expedition_claim(mid: int, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    m = await monsters.get_owned(db, user, mid)
    r = await monsters.claim_expedition(db, user, m)
    await db.commit()
    return r


class ExchangeIn(BaseModel):
    src: str
    dst: str
    amount: int


@router.post("/exchange")
async def exchange(body: ExchangeIn, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    r = await monsters.exchange(db, user, body.src, body.dst, body.amount)
    await db.commit()
    return r


@router.get("/capsules")
async def capsules(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Capsule).where(Capsule.user_id == user.id, Capsule.opened_at.is_(None))
                             .order_by(Capsule.id))).scalars()
    return [{"id": c.id, "type": c.type, "source": c.source} for c in rows]


@router.post("/capsules/{cid}/open")
async def open_capsule(cid: int, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    c = await db.get(Capsule, cid)
    if c is None:
        raise HTTPException(404, "캡슐을 찾을 수 없습니다")
    r = await monsters.open_capsule(db, user, c)
    await db.commit()
    return r


@router.get("/bag")
async def bag(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    items = await actions.bag_items(db, user)
    g = data.guides()
    names = data.items_by_label()
    exp_days = data.economy()["verify"]["bag_expire_days"]
    out = {"capacity": economy.bag_capacity(user), "expire_days": exp_days,
           "items": [{"id": it.id, "category": it.category, "category_name": g["categories"][it.category]["name"],
                      "item_name": names.get(it.item_label or "", {}).get("name"), "type": it.type,
                      "clean": it.is_clean, "habit_ok": it.habit_ok, "at": it.created_at.isoformat()}
                     for it in items]}
    await db.commit()
    return out


@router.get("/dex")
async def dex(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    entries = await economy.dex(db, user)
    have = {(e.kind, e.ref): e for e in entries}
    sp = data.species()
    mons = []
    for lid, ln in sp["lines"].items():
        for st in range(1, ln.get("max_stage", 3) + 1):
            e = have.get(("monster", f"{lid}_{st}"))
            mons.append({"ref": f"{lid}_{st}", "species": lid, "stage": st, "name": ln["names"][st - 1],
                         "type": ln["type"], "rarity": ln["rarity"], "have": e is not None,
                         "shiny": bool(e and e.is_shiny)})
    g = data.guides()
    items = [{"ref": it["label"], "name": it["name"], "category": it["category"],
              "category_name": g["categories"][it["category"]]["name"], "have": ("item", it["label"]) in have}
             for it in g["items"]]
    stamps = [e.ref for e in entries if e.kind == "stamp"]
    return {"monsters": mons, "items": items, "stamps": stamps}


@router.get("/missions")
async def get_missions(user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    r = await missions.status(db, user)
    await db.commit()
    return r


@router.post("/missions/{mission_id}/claim")
async def claim_mission(mission_id: str, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    r = await missions.claim(db, user, mission_id)
    await db.commit()
    return r


class MatChoiceIn(BaseModel):
    material: str


@router.post("/missions/types3/material")
async def claim_types3(body: MatChoiceIn, user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    r = await missions.claim_weekly_materials(db, user, body.material)
    await db.commit()
    return r
