"""리몬: 능력치, 레벨업, 진화, 캡슐(뽑기), 파티, 탐사, 재료 교환."""
import random
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Capsule, User, UserMonster
from app.services.clock import now
from app.services.game import data, economy


def sp() -> dict:
    return data.species()


def max_stage(line_id: str) -> int:
    return data.line(line_id).get("max_stage", 3)


def level_cap(m: UserMonster) -> int:
    caps = sp()["level_cap"]
    if max_stage(m.species) == 1:          # 진화하지 않는 전설은 처음부터 마지막 단계 상한
        return caps[-1]
    return caps[m.stage - 1]


def stats(m: UserMonster) -> dict:
    ln = data.line(m.species)
    role = sp()["roles"][ln["role"]]
    k = (1 + 0.06 * (m.level - 1)) * sp()["stage_mult"][m.stage - 1] * sp()["rarity_mult"][ln["rarity"]] \
        * (1 + 0.05 * m.stars)
    return {s: int(round(role[s] * k)) for s in ("hp", "atk", "def", "spd")}


def power(m: UserMonster) -> int:
    s = stats(m)
    return int(s["hp"] * 0.5 + s["atk"] * 2 + s["def"] + s["spd"] * 0.5)


def view(m: UserMonster, habit_counts: dict[str, int] | None = None) -> dict:
    ln = data.line(m.species)
    skill = sp()["skills"][sp()["roles"][ln["role"]]["skill"]]
    out = {
        "id": m.id, "species": m.species, "name": ln["names"][m.stage - 1], "type": ln["type"],
        "rarity": ln["rarity"], "role": ln["role"], "stage": m.stage, "level": m.level, "level_cap": level_cap(m),
        "stars": m.stars, "is_shiny": m.is_shiny, "slot": m.slot, "skill_timing": m.skill_timing,
        "art": f"{m.species}_{m.stage}", "stats": stats(m), "power": power(m),
        "skill": skill, "desc": ln["desc"],
        "on_expedition": bool(m.expedition_until),
        "expedition_until": m.expedition_until.isoformat() if m.expedition_until else None,
        "levelup_cost": levelup_cost(m) if m.level < level_cap(m) else None,
    }
    ev = evolve_rule(m)
    if ev:
        out["evolve"] = {**ev, "habit_now": (habit_counts or {}).get(habit_type(m), 0)}
    return out


def habit_type(m: UserMonster) -> str:
    return data.line(m.species)["type"]


def levelup_cost(m: UserMonster) -> dict:
    lu = data.economy()["levelup"]
    return {"material": data.line(m.species)["type"] if data.line(m.species)["type"] != "spirit" else "plastic",
            "materials": lu["mat_base"] + m.level, "coins": lu["coin_per_level"] * m.level}


def evolve_rule(m: UserMonster) -> dict | None:
    if m.stage >= max_stage(m.species):
        return None
    for r in data.economy()["evolve"]:
        if r["to_stage"] == m.stage + 1:
            return dict(r)
    return None


async def get_owned(db: AsyncSession, user: User, monster_id: int) -> UserMonster:
    m = await db.get(UserMonster, monster_id)
    if m is None or m.user_id != user.id:
        raise HTTPException(404, "리몬을 찾을 수 없습니다")
    return m


async def list_owned(db: AsyncSession, user: User) -> list[UserMonster]:
    q = select(UserMonster).where(UserMonster.user_id == user.id).order_by(UserMonster.id)
    return list((await db.execute(q)).scalars())


async def level_up(db: AsyncSession, user: User, m: UserMonster) -> dict:
    if m.level >= level_cap(m):
        if evolve_rule(m) is None:
            raise HTTPException(400, "최대 레벨이에요")
        raise HTTPException(400, "이 단계의 최대 레벨입니다. 진화가 필요해요")
    c = levelup_cost(m)
    await economy.add_resource(db, user, f"mat:{c['material']}", -c["materials"], "levelup", str(m.id), scale=False)
    await economy.add_resource(db, user, "coins", -c["coins"], "levelup", str(m.id), scale=False)
    m.level += 1
    d = await economy.daily(db, user)
    d.levelup_count += 1
    return {"level": m.level}


async def evolve(db: AsyncSession, user: User, m: UserMonster) -> dict:
    r = evolve_rule(m)
    if r is None:
        raise HTTPException(400, "더 진화할 수 없습니다")
    if m.level < r["level"]:
        raise HTTPException(400, f"Lv{r['level']}이 되어야 진화할 수 있어요")
    hab = (await economy.habits(db, user)).get(habit_type(m), 0)
    if hab < r["habits"]:
        h = data.guides()["habits"].get(habit_type(m), {}).get("name", "올바른 습관")
        raise HTTPException(400, f"'{h}' 스캔을 {r['habits']}번 해야 진화해요 (지금 {hab}번)")
    mat = levelup_cost(m)["material"]
    await economy.add_resource(db, user, f"mat:{mat}", -r["materials"], "evolve", str(m.id), scale=False)
    if r["crystals"]:
        await economy.add_resource(db, user, "crystals", -r["crystals"], "evolve", str(m.id))
    m.stage += 1
    await economy.add_dex(db, user, "monster", f"{m.species}_{m.stage}", m.is_shiny)
    return {"stage": m.stage, "name": data.line(m.species)["names"][m.stage - 1]}


# ───────── 캡슐 ─────────
async def grant_capsule(db: AsyncSession, user: User, type_: str, source: str, bonus_rare: float = 0.0) -> Capsule:
    c = Capsule(user_id=user.id, type=type_, source=source, bonus_rare=bonus_rare)
    db.add(c)
    await db.flush()
    return c


async def _new_monster(db: AsyncSession, user: User, line_id: str, shiny: bool) -> tuple[UserMonster, bool]:
    """반환: (리몬, 중복 여부). 중복이면 별 +1 (최대치면 재료로 바꾸고 m._overflow 에 기록)."""
    existing = (await db.execute(select(UserMonster).where(
        UserMonster.user_id == user.id, UserMonster.species == line_id))).scalars().first()
    if existing:
        cap = data.economy()["capsule"]["max_stars"]
        existing._overflow = None  # type: ignore[attr-defined]
        if existing.stars < cap:
            existing.stars += 1
        else:
            mat = data.line(line_id)["type"]
            got = await economy.add_resource(db, user, f"mat:{mat}",
                                             data.economy()["capsule"]["dup_overflow_materials"], "dup_overflow",
                                             line_id)
            existing._overflow = {"material": mat, "amount": got}  # type: ignore[attr-defined]
        if shiny and not existing.is_shiny:
            existing.is_shiny = True
            await economy.add_dex(db, user, "monster", f"{line_id}_{existing.stage}", True)
        return existing, True
    m = UserMonster(user_id=user.id, species=line_id, stage=1, level=1, stars=0, is_shiny=shiny,
                    skill_timing="now")
    db.add(m)
    await db.flush()
    await economy.add_dex(db, user, "monster", f"{line_id}_1", shiny)
    return m, False


async def open_capsule(db: AsyncSession, user: User, cap: Capsule, rng: random.Random | None = None) -> dict:
    if cap.user_id != user.id:
        raise HTTPException(404, "캡슐을 찾을 수 없습니다")
    if cap.opened_at is not None:
        return cap.result_json or {}
    rng = rng or random.Random()
    cfg = data.economy()["capsule"]
    pool = sp()["capsule_pool"][cap.type]
    if "epic" in pool:
        line_id, rarity = pool["epic"], "epic"
    else:
        rare = user.pity + 1 >= cfg["pity"] or rng.random() < cfg["rare_rate"] + cap.bonus_rare
        line_id, rarity = (pool["rare"], "rare") if rare else (pool["common"], "common")
        user.pity = 0 if rare else user.pity + 1
    shiny_rate = cfg["shiny_clean_rate"] if cap.bonus_rare > 0 else cfg["shiny_rate"]
    shiny = rng.random() < shiny_rate
    m, dup = await _new_monster(db, user, line_id, shiny)
    stage = m.stage if dup else 1
    cap.opened_at = now()
    cap.result_monster_id = m.id
    result = {"monster_id": m.id, "species": line_id, "name": data.line(line_id)["names"][stage - 1],
              "rarity": rarity, "shiny": shiny, "duplicate": dup, "stars": m.stars,
              "art": f"{line_id}_{stage}", "type": data.line(line_id)["type"],
              "overflow": getattr(m, "_overflow", None) if dup else None}
    legend = await check_legend(db, user)
    if legend:
        result["legend"] = legend
    cap.result_json = result
    return result


async def check_legend(db: AsyncSession, user: User) -> dict | None:
    """일반·희귀 10종을 모두 모으면 전설 지급. 지급했으면 보여 줄 정보를 돌려준다."""
    have = {m.species for m in await list_owned(db, user)}
    if "reverse" in have:
        return None
    need = {v for pool in sp()["capsule_pool"].values() for k, v in pool.items() if k in ("common", "rare")}
    if need <= have:
        m, _ = await _new_monster(db, user, "reverse", False)
        return {"monster_id": m.id, "name": data.line("reverse")["names"][0], "art": "reverse_1"}
    return None


async def choose_starter(db: AsyncSession, user: User, line_id: str) -> UserMonster:
    if user.starter_done:
        raise HTTPException(400, "이미 첫 리몬을 골랐어요")
    if line_id not in sp()["starters"]:
        raise HTTPException(400, "고를 수 없는 리몬입니다")
    m, _ = await _new_monster(db, user, line_id, False)
    m.slot = 0
    user.starter_done = True
    return m


# ───────── 파티 ─────────
async def set_party(db: AsyncSession, user: User, ids: list[int | None], timings: dict[int, str]) -> None:
    if len(ids) != 3:
        raise HTTPException(400, "파티는 3자리입니다")
    owned = {m.id: m for m in await list_owned(db, user)}
    chosen = [i for i in ids if i is not None]
    if len(set(chosen)) != len(chosen) or any(i not in owned for i in chosen):
        raise HTTPException(400, "파티 구성이 올바르지 않습니다")
    if not chosen:
        raise HTTPException(400, "리몬을 1마리 이상 넣어 주세요")
    for m in owned.values():
        m.slot = None
    for slot, i in enumerate(ids):
        if i is not None:
            if owned[i].expedition_until:
                raise HTTPException(400, "탐사 중인 리몬은 파티에 넣을 수 없어요")
            owned[i].slot = slot
    for mid, t in timings.items():
        if mid in owned and t in ("now", "boss50", "ally30"):
            owned[mid].skill_timing = t


async def party(db: AsyncSession, user: User) -> list[UserMonster]:
    ms = [m for m in await list_owned(db, user) if m.slot is not None and not m.expedition_until]
    return sorted(ms, key=lambda m: m.slot or 0)


# ───────── 탐사 ─────────
async def send_expedition(db: AsyncSession, user: User, m: UserMonster) -> dict:
    economy.require(user, "expedition")
    slots = 2 if economy.unlocked(user, "expedition2") else 1
    busy = [x for x in await list_owned(db, user) if x.expedition_until]
    if m.expedition_until:
        raise HTTPException(400, "이미 탐사 중이에요")
    if len(busy) >= slots:
        raise HTTPException(400, f"탐사는 {slots}마리까지 보낼 수 있어요")
    m.expedition_until = now() + timedelta(hours=data.economy()["expedition"]["hours"])
    m.slot = None
    d = await economy.daily(db, user)
    d.expedition_sent += 1
    return {"until": m.expedition_until.isoformat()}


async def claim_expedition(db: AsyncSession, user: User, m: UserMonster) -> dict:
    if not m.expedition_until:
        raise HTTPException(400, "탐사 중이 아니에요")
    if m.expedition_until > now():
        raise HTTPException(400, "아직 탐사 중이에요")
    cfg = data.economy()["expedition"]
    t = data.line(m.species)["type"]
    mat = t if t in data.MATERIALS else "plastic"
    got_m = await economy.add_resource(db, user, f"mat:{mat}", cfg["materials"], "expedition", str(m.id))
    got_c = await economy.add_resource(db, user, "coins", cfg["coins"], "expedition", str(m.id))
    m.expedition_until = None
    # 파티에 빈자리가 있으면 돌아온 리몬을 다시 넣는다
    used = {x.slot for x in await list_owned(db, user) if x.slot is not None}
    free = next((s for s in (0, 1, 2) if s not in used), None)
    if free is not None:
        m.slot = free
    return {"material": mat, "materials": got_m, "coins": got_c, "slot": m.slot}


# ───────── 재료 교환 ─────────
async def exchange(db: AsyncSession, user: User, src: str, dst: str, amount: int) -> dict:
    economy.require(user, "exchange")
    cfg = data.economy()["exchange"]
    if amount <= 0 or amount > 1000 or dst not in data.BASE_TYPES:
        raise HTTPException(400, "기본 재료(플라스틱·종이·금속·유리·비닐)로만 바꿀 수 있어요")
    if src == "coins":
        cost = amount * cfg["coin_per_material"]
        await economy.add_resource(db, user, "coins", -cost, "exchange", dst, scale=False)
    else:
        if src not in data.BASE_TYPES or src == dst:
            raise HTTPException(400, "교환할 수 없습니다")
        cost = amount * cfg["material_ratio"]
        await economy.add_resource(db, user, f"mat:{src}", -cost, "exchange", dst, scale=False)
    await economy.add_resource(db, user, f"mat:{dst}", amount, "exchange", src, scale=False)
    return {"spent": cost, "got": amount}
