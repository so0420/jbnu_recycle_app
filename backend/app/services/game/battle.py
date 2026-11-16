"""자동 전투 엔진. DB 를 모르는 순수 함수: simulate(party, boss, seed) -> 결과 + 전투 기록.

프론트는 log 를 받아 그대로 재생만 한다(카드 흔들림·숫자·체력바).
"""
import random
from dataclasses import dataclass, field

from app.services.game import data

BASE_TYPES = ["plastic", "paper", "metal", "glass", "vinyl"]
MAX_ROUNDS = 15


@dataclass
class Unit:
    uid: str
    name: str
    side: str            # ally | enemy
    type: str
    role: str
    hp: float
    max_hp: float
    atk: float
    def_: float
    spd: float
    skill: str | None = None
    timing: str = "now"
    front: bool = False
    art: str = ""
    shield: float = 0.0
    stun: int = 0
    taunt: int = 0
    dr: float = 0.0          # 받는 피해 감소율
    dr_rounds: int = 0
    def_buff: int = 0
    slow: float = 0.0
    pollution: int = 0
    charge: int = 0          # 3이 되면 스킬 사용 가능

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def public(self) -> dict:
        return {"id": self.uid, "name": self.name, "side": self.side, "type": self.type, "hp": round(self.hp),
                "max_hp": round(self.max_hp), "front": self.front, "art": self.art}


@dataclass
class Result:
    damage: int
    boss_killed: bool
    rounds: int
    wiped: bool
    units: list[dict]
    log: list[dict] = field(default_factory=list)


def type_mult(att: str, dfn: str, weak: str | None) -> float:
    beats = data.species()["type_beats"]
    if weak and att == weak:
        return 1.5
    if beats.get(att) == dfn:
        return 1.5
    if beats.get(dfn) == att:
        return 0.75
    return 1.0


def make_ally(uid: str, view: dict, front: bool) -> Unit:
    role = data.species()["roles"][view["role"]]
    s = view["stats"]
    return Unit(uid=uid, name=view["name"], side="ally", type=view["type"], role=view["role"], hp=s["hp"],
                max_hp=s["hp"], atk=s["atk"], def_=s["def"], spd=s["spd"], skill=role["skill"],
                timing=view.get("skill_timing", "now"), front=front, art=view["art"])


def make_boss(key: str, battle_hp: float, party_atk_sum: float) -> list[Unit]:
    b = data.bosses()["bosses"][key]
    if b["gimmick"] == "swarm":
        mini_hp = max(60.0, party_atk_sum * 0.9)
        return [Unit(uid=f"b{i}", name=f"{b['name']} {i + 1}", side="enemy", type="plastic", role="boss",
                     hp=mini_hp, max_hp=mini_hp, atk=b["atk"], def_=b["def"], spd=b["spd"] + i, art=key)
                for i in range(5)]
    u = Unit(uid="b0", name=b["name"], side="enemy", type="boss", role="boss", hp=battle_hp, max_hp=battle_hp,
             atk=b["atk"], def_=b["def"], spd=b["spd"], art=key)
    if b["gimmick"] == "label_shield":
        u.shield = party_atk_sum * 2.5
    return [u]


def simulate(party: list[Unit], boss_key: str, battle_hp: float, seed: int, boss_hp_ratio: float = 1.0) -> Result:
    rng = random.Random(seed)
    bcfg = data.bosses()["bosses"][boss_key]
    gimmick = bcfg["gimmick"]
    atk_sum = sum(u.atk for u in party)
    enemies = make_boss(boss_key, battle_hp, atk_sum)
    shield_max = enemies[0].shield
    start_units = [u.public() for u in party] + [e.public() for e in enemies]
    log: list[dict] = []
    total = 0.0
    killed = False
    respawns = 0

    def alive(side: str) -> list[Unit]:
        return [u for u in (party if side == "ally" else enemies) if u.alive]

    def weak_now(rnd: int) -> str | None:
        if gimmick == "rotate_weak":
            return BASE_TYPES[((rnd - 1) // 3) % 5]
        w = bcfg.get("weak")
        return w if w in BASE_TYPES else None

    def hit(att: Unit, tgt: Unit, mult: float, rnd: int, crit_rate: float = 0.05, act: str = "basic") -> float:
        nonlocal total
        crit = rng.random() < crit_rate
        defense = tgt.def_ * (1.2 if tgt.def_buff > 0 else 1.0)
        atk = att.atk * (1 - 0.05 * att.pollution) * (1 - att.slow)
        dmg = atk * mult * 100 / (100 + defense) * rng.uniform(0.9, 1.1)
        if att.side == "ally":
            dmg *= type_mult(att.type, tgt.type if tgt.type != "boss" else "", weak_now(rnd))
        if crit:
            dmg *= 1.5
        ev = {"r": rnd, "a": att.uid, "act": act, "t": tgt.uid, "crit": crit}
        if tgt.side == "enemy" and tgt.shield > 0:
            brk = dmg * (2 if att.type == "glass" else 1)
            tgt.shield = max(0.0, tgt.shield - brk)
            ev["shield_hit"] = round(brk)
            dmg *= 0.3
        if tgt.side == "ally":
            dmg *= (1 - tgt.dr)
            if tgt.shield > 0:
                absorbed = min(tgt.shield, dmg)
                tgt.shield -= absorbed
                dmg -= absorbed
                ev["absorbed"] = round(absorbed)
        dmg = min(dmg, tgt.hp)
        tgt.hp -= dmg
        ev["dmg"] = round(dmg)
        if not tgt.alive:
            ev["kill"] = True
        if att.side == "ally":
            total += dmg
        log.append(ev)
        return dmg

    def pick_enemy_target() -> Unit | None:
        al = alive("ally")
        if not al:
            return None
        taunters = [u for u in al if u.taunt > 0]
        if taunters:
            return taunters[0]
        fronts = [u for u in al if u.front]
        if fronts and rng.random() < 0.7:
            return fronts[0]
        return rng.choice(al)

    def skill_ok(u: Unit) -> bool:
        if u.charge < 3:
            return False
        if u.timing == "boss50":
            cur = sum(e.hp for e in enemies) / max(1.0, sum(e.max_hp for e in enemies))
            return min(cur, boss_hp_ratio) <= 0.5 or boss_hp_ratio <= 0.5
        if u.timing == "ally30":
            return any(a.alive and a.hp / a.max_hp <= 0.3 for a in party) or u.skill in ("shards", "discharge",
                                                                                        "bind", "crush")
        return True

    for rnd in range(1, MAX_ROUNDS + 1):
        order = sorted([u for u in party + enemies if u.alive], key=lambda x: -x.spd * (1 - x.slow))
        for u in order:
            if not u.alive:
                continue
            if not alive("enemy") or not alive("ally"):
                break
            if u.stun > 0:
                u.stun -= 1
                log.append({"r": rnd, "a": u.uid, "act": "stunned"})
                continue
            if u.side == "ally":
                u.charge += 1
                foes = alive("enemy")
                if u.skill and skill_ok(u):
                    u.charge = 0
                    s = u.skill
                    log.append({"r": rnd, "a": u.uid, "act": "skill", "skill": s})
                    if s == "crush":
                        u.taunt, u.dr, u.dr_rounds = 2, 0.3, 2
                        hit(u, foes[0], 1.0, rnd, act="crush")
                    elif s == "shards":
                        for f in foes:
                            hit(u, f, 0.8, rnd, crit_rate=0.3, act="shards")
                    elif s == "regen":
                        tgt = min(alive("ally"), key=lambda a: a.hp / a.max_hp)
                        heal = min(u.atk * 1.5, tgt.max_hp - tgt.hp)
                        tgt.hp += heal
                        for a in party:
                            a.pollution = 0
                        log.append({"r": rnd, "a": u.uid, "act": "heal", "t": tgt.uid, "heal": round(heal),
                                    "cleanse": True})
                    elif s == "wrap":
                        for a in alive("ally"):
                            a.shield += u.atk * 1.0
                        log.append({"r": rnd, "a": u.uid, "act": "shield_all", "amount": round(u.atk)})
                    elif s == "bind":
                        f = foes[0] if len(foes) == 1 else rng.choice(foes)
                        if f.uid == "b0" and len(enemies) == 1:
                            f.slow = min(0.6, f.slow + 0.3)
                        else:
                            f.stun = 1
                        hit(u, f, 0.8, rnd, act="bind")
                    elif s == "discharge":
                        for _ in range(3):
                            fs = alive("enemy")
                            if fs:
                                hit(u, rng.choice(fs), 0.7, rnd, act="discharge")
                    elif s == "patch":
                        for a in alive("ally"):
                            h = min(u.atk * 0.6, a.max_hp - a.hp)
                            a.hp += h
                            a.def_buff = 2
                        log.append({"r": rnd, "a": u.uid, "act": "heal_all", "amount": round(u.atk * 0.6)})
                    elif s == "cycle":
                        for f in foes:
                            hit(u, f, 0.9, rnd, act="cycle")
                        for a in alive("ally"):
                            a.hp = min(a.max_hp, a.hp + u.atk * 0.4)
                else:
                    tgt = min(foes, key=lambda f: f.hp) if len(foes) > 1 else foes[0]
                    hit(u, tgt, 1.0, rnd)
            else:
                if gimmick == "slam" and rnd % 3 == 0:
                    log.append({"r": rnd, "a": u.uid, "act": "slam"})
                    for a in alive("ally"):
                        hit(u, a, 1.6, rnd, act="slam")
                else:
                    tgt = pick_enemy_target()
                    if tgt:
                        hit(u, tgt, 1.0, rnd)
        # 라운드 끝 처리
        if not alive("ally"):
            break
        if not alive("enemy"):
            if gimmick == "swarm":
                respawns += 1
                for e in enemies:
                    e.hp = e.max_hp
                log.append({"r": rnd, "act": "respawn"})
            else:
                killed = True
                break
        if gimmick == "pollution":
            for a in alive("ally"):
                a.pollution = min(10, a.pollution + 1)
            log.append({"r": rnd, "act": "pollute"})
        if gimmick == "label_shield" and rnd == 8 and shield_max:
            enemies[0].shield = shield_max
            log.append({"r": rnd, "act": "reshield"})
        for a in party:
            a.taunt = max(0, a.taunt - 1)
            a.def_buff = max(0, a.def_buff - 1)
            if a.dr_rounds:
                a.dr_rounds -= 1
                if a.dr_rounds == 0:
                    a.dr = 0.0
        for e in enemies:
            e.slow = max(0.0, e.slow - 0.1)

    return Result(damage=int(total), boss_killed=killed, rounds=rnd, wiped=not alive("ally"),
                  units=start_units, log=log)
