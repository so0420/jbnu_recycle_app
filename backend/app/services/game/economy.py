"""자원·경험치·레벨·도감·일일/주간 기록. 모든 변경은 economy_events 에 남긴다."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import DexEntry, EconomyEvent, HabitProgress, User, UserDaily, UserMaterial, UserWeekly
from app.services.clock import today, week_start
from app.services.game import data


async def ensure_row(db: AsyncSession, model, pk: tuple, **values):
    """동시 요청에도 안전한 get-or-create: INSERT IGNORE 후 최신 값으로 다시 읽는다."""
    await db.execute(mysql_insert(model).values(**values).prefix_with("IGNORE"))
    return await db.get(model, pk, populate_existing=True)


def eco() -> dict:
    return data.economy()


def mult(n: int | float) -> int:
    return int(round(n * settings.ECONOMY_MULTIPLIER))


# ───────── 계정 레벨 (정원) ─────────
def need_xp(level: int) -> int:
    a = eco()["account_xp"]
    return a["need_base"] + a["need_step"] * level


def level_from_xp(xp: int) -> int:
    lv = 1
    while xp >= need_xp(lv):
        xp -= need_xp(lv)
        lv += 1
    return lv


def xp_progress(xp: int) -> tuple[int, int]:
    """(현재 레벨 안에서 쌓인 XP, 다음 레벨까지 필요한 XP)"""
    lv = 1
    while xp >= need_xp(lv):
        xp -= need_xp(lv)
        lv += 1
    return xp, need_xp(lv)


def garden_stage(level: int) -> int:
    return 4 if level >= 15 else 3 if level >= 7 else 2 if level >= 3 else 1


def unlocked(user: User, feature: str) -> bool:
    return user.level >= eco()["garden"].get(feature, 1)


def require(user: User, feature: str) -> None:
    if not unlocked(user, feature):
        need = eco()["garden"][feature]
        raise HTTPException(403, f"정원 레벨 {need}에 열립니다")


def bag_capacity(user: User) -> int:
    g = eco()["garden"]
    base = 15 if user.level >= g["bag15"] else 10 if user.level >= g["bag10"] else 6
    return base + (user.bag_capacity - 6)          # 도감 보상으로 늘어난 칸


async def add_xp(db: AsyncSession, user: User, amount: int, reason: str, ref: str | None = None) -> dict:
    amount = mult(amount)
    before = user.level
    user.xp += amount
    user.level = level_from_xp(user.xp)
    db.add(EconomyEvent(user_id=user.id, resource="xp", delta=amount, reason=reason, ref=ref))
    return {"xp": amount, "level_before": before, "level_after": user.level}


# ───────── 재화 ─────────
async def add_resource(db: AsyncSession, user: User, resource: str, delta: int, reason: str,
                       ref: str | None = None, scale: bool = True) -> int:
    """resource: coins | tickets | crystals | mat:<type>. 반환: 실제 변경량"""
    if scale and delta > 0 and resource != "tickets" and resource != "crystals":
        delta = mult(delta)
    if delta == 0:
        return 0
    if resource == "coins":
        if user.coins + delta < 0:
            raise HTTPException(400, "코인이 부족합니다")
        user.coins += delta
    elif resource == "tickets":
        cap = eco()["tickets"]["cap"]
        if delta > 0:
            delta = max(0, min(delta, cap - user.tickets))
            if delta == 0:
                return 0
        elif user.tickets + delta < 0:
            raise HTTPException(400, "도전권이 부족합니다")
        user.tickets += delta
    elif resource == "crystals":
        if user.crystals + delta < 0:
            raise HTTPException(400, "정화의 결정이 부족합니다")
        user.crystals += delta
    elif resource.startswith("mat:"):
        mat = resource[4:]
        row = await ensure_row(db, UserMaterial, (user.id, mat), user_id=user.id, material=mat, amount=0)
        if row.amount + delta < 0:
            raise HTTPException(400, f"{material_name(mat)} 재료가 부족합니다")
        row.amount += delta
    else:
        raise ValueError(resource)
    db.add(EconomyEvent(user_id=user.id, resource=resource, delta=delta, reason=reason, ref=ref))
    return delta


async def materials(db: AsyncSession, user: User) -> dict[str, int]:
    rows = (await db.execute(select(UserMaterial).where(UserMaterial.user_id == user.id))).scalars()
    out = {m: 0 for m in data.MATERIALS}
    for r in rows:
        out[r.material] = r.amount
    return out


MATERIAL_NAMES = {"plastic": "플라스틱 칩", "paper": "펄프", "metal": "알루미늄", "glass": "유리 조각",
                  "vinyl": "비닐 필름", "volt": "볼트 코어", "fabric": "섬유 실"}


def material_name(mat: str) -> str:
    return MATERIAL_NAMES.get(mat, mat)


# ───────── 일일·주간 기록 ─────────
async def daily(db: AsyncSession, user: User) -> UserDaily:
    row = await db.get(UserDaily, (user.id, today()))
    if row is None:
        row = await ensure_row(db, UserDaily, (user.id, today()), user_id=user.id, day=today(), verify_count=0,
                               guide_xp_count=0, ai_calls=0, free_raid_used=False, dumpday_ticket=False,
                               raid_count=0, levelup_count=0, expedition_sent=0, scan_count=0,
                               missions_claimed=[])
    return row


async def weekly(db: AsyncSession, user: User) -> UserWeekly:
    ws = week_start()
    row = await db.get(UserWeekly, (user.id, ws))
    if row is None:
        row = await ensure_row(db, UserWeekly, (user.id, ws), user_id=user.id, week_start=ws, verify_count=0,
                               types=[], habit_count=0, claimed=[])
    return row


async def add_habit(db: AsyncSession, user: User, type_: str) -> int:
    row = await ensure_row(db, HabitProgress, (user.id, type_), user_id=user.id, type=type_, count=0)
    row.count += 1
    w = await weekly(db, user)
    w.habit_count += 1
    return row.count


async def habits(db: AsyncSession, user: User) -> dict[str, int]:
    rows = (await db.execute(select(HabitProgress).where(HabitProgress.user_id == user.id))).scalars()
    return {r.type: r.count for r in rows}


# ───────── 도감 ─────────
async def add_dex(db: AsyncSession, user: User, kind: str, ref: str, shiny: bool = False) -> bool:
    """새로 채웠으면 True. 새로 채우면 도감 완성 보상도 확인한다."""
    res = await db.execute(mysql_insert(DexEntry).values(user_id=user.id, kind=kind, ref=ref, is_shiny=shiny)
                           .prefix_with("IGNORE"))
    new = res.rowcount == 1
    if not new:
        if shiny:
            row = await db.get(DexEntry, (user.id, kind, ref), populate_existing=True)
            if row and not row.is_shiny:
                row.is_shiny = True
        return False
    await _dex_rewards(db, user, kind, ref)
    return True


async def _claim_once(db: AsyncSession, user: User, key: str) -> bool:
    res = await db.execute(mysql_insert(DexEntry).values(user_id=user.id, kind="reward", ref=key, is_shiny=False)
                           .prefix_with("IGNORE"))
    return res.rowcount == 1


async def _dex_rewards(db: AsyncSession, user: User, kind: str, ref: str) -> None:
    have = {(e.kind, e.ref) for e in await dex(db, user)}
    if kind == "item":
        items = data.guides()["items"]
        cat = next((it["category"] for it in items if it["label"] == ref), None)
        same = [it["label"] for it in items if it["category"] == cat]
        if cat and all(("item", lbl) in have for lbl in same) and await _claim_once(db, user, f"itemcat:{cat}"):
            user.bag_capacity += 1          # 분류별 품목 도감 완성 → 가방 +1칸
            db.add(EconomyEvent(user_id=user.id, resource="bag_capacity", delta=1, reason="dex_item", ref=cat))
    elif kind == "monster":
        line_id = ref.rsplit("_", 1)[0]
        lines = data.species()["lines"]
        t = lines.get(line_id, {}).get("type")
        if t not in data.BASE_TYPES:
            return
        refs = [f"{lid}_{st}" for lid, ln in lines.items() if ln["type"] == t and ln["rarity"] in ("common", "rare")
                for st in range(1, ln.get("max_stage", 3) + 1)]
        if all(("monster", r) in have for r in refs) and await _claim_once(db, user, f"montype:{t}"):
            await add_resource(db, user, f"mat:{t}", 50, "dex_type", t)   # 타입별 리몬 도감 완성 → 재료 50


async def dex(db: AsyncSession, user: User) -> list[DexEntry]:
    return list((await db.execute(select(DexEntry).where(DexEntry.user_id == user.id))).scalars())
