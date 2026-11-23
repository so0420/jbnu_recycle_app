"""지역 공방전: 공격권 지급, 피해 계산(인구 보정·역전·피로·위기), 제한, 소식."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Place, Region, RegionEvent, RegionState, User, Verification
from app.services.clock import now, week_start
from app.services.game import actions, region
from app.services.game import attack as attack_svc

# 시·군·구 3곳(인구 1만·3만·2만, 평균 2만) + 이번 주에 인증이 없는 1곳
UNITS = [("T000000001", "T0001", "가시", 10000), ("T000000002", "T0002", "나시", 30000),
         ("T000000003", "T0003", "다시", 20000), ("T000000004", "T0004", "라시", 20000)]


@pytest.fixture(autouse=True)
def _sigungu_mode(monkeypatch):
    monkeypatch.setattr(region.settings, "REGION_MODE", "sigungu")
    region.invalidate_units()
    yield
    region.invalidate_units()


async def _world(db, clean=(500, 700, 300), tickets=3):
    for code, sgg, gu, pop in UNITS:
        db.add(Region(code=code, name=gu + "동", gu=gu, sido="테스트도", sigungu_code=sgg, population=pop,
                      center_lat=35.8, center_lng=127.1, neighbors="", dump_weekdays=""))
    ws = week_start()
    for (code, sgg, _, _), c in zip(UNITS[:3], clean):
        db.add(RegionState(week_start=ws, unit=f"S{sgg}", cleanliness=float(c), verifs=1))
    me = User(login_id="atk_a", password_hash="!", nickname="공격자", region_code=UNITS[0][0],
              region_confirmed_at=now(), attack_tickets=tickets)
    other = User(login_id="atk_b", password_hash="!", nickname="수비자", region_code=UNITS[1][0],
                 region_confirmed_at=now())
    db.add_all([me, other])
    await db.flush()
    return me


async def _clean(db, unit):
    return (await db.get(RegionState, (week_start(), unit), populate_existing=True)).cleanliness


async def test_attack_damage_and_modifiers(db_session):
    db = db_session
    me = await _world(db)
    # 기준 회복량 40 (활성 3곳, 인증 3건) × 1.5 × 인구 보정 2.0(평균 2만 / 1만) = 120
    assert await attack_svc.base_damage(db, "ST0001") == pytest.approx(120)

    # 순위: 나시(700) 1위, 가시(500) 2위 → 우리보다 높은 지역이면 ×1.2
    r = await attack_svc.attack(db, me, "ST0002")
    assert r["damage"] == pytest.approx(144)
    assert r["mods"] == ["underdog"]
    assert await _clean(db, "ST0002") == pytest.approx(556)
    assert me.attack_tickets == 2
    await db.flush()

    # 다시(300)는 3위: 보정 없이 120
    r = await attack_svc.attack(db, me, "ST0003")
    assert (r["damage"], r["mods"]) == (pytest.approx(120), [])
    await db.flush()
    # 오늘 이미 120 맞았고(피로 ×0.5), 이제 180이라 위기(×0.5) → 30
    r = await attack_svc.attack(db, me, "ST0003")
    assert r["damage"] == pytest.approx(30)
    assert set(r["mods"]) == {"fatigue", "crisis"}
    assert me.attack_tickets == 0
    await db.flush()

    ev = (await db.execute(select(RegionEvent).where(RegionEvent.type == "attack"))).scalars().all()
    assert len(ev) == 3 and all(e.src_unit == "ST0001" and e.user_id == me.id for e in ev)


async def test_attack_limits(db_session):
    db = db_session
    me = await _world(db, tickets=5)
    for target, msg in [("ST0001", "우리 동네"), ("ST0004", "이번 주에"), ("SNOPE", "찾을 수 없")]:
        with pytest.raises(HTTPException) as e:
            await attack_svc.attack(db, me, target)
        assert msg in e.value.detail
    await attack_svc.attack(db, me, "ST0003")
    await db.flush()
    await attack_svc.attack(db, me, "ST0003")
    await db.flush()
    with pytest.raises(HTTPException) as e:
        await attack_svc.attack(db, me, "ST0003")
    assert "하루에 2번" in e.value.detail
    assert me.attack_tickets == 3          # 실패한 공격은 공격권을 쓰지 않는다

    me.attack_tickets = 0
    with pytest.raises(HTTPException) as e:
        await attack_svc.attack(db, me, "ST0002")
    assert "공격권이 없어요" in e.value.detail

    me.attack_tickets = 1
    me.region_confirmed_at = None
    with pytest.raises(HTTPException) as e:
        await attack_svc.attack(db, me, "ST0002")
    assert "확정" in e.value.detail


async def test_overview_and_feed(db_session):
    db = db_session
    me = await _world(db)
    ov = await attack_svc.overview(db, me)
    assert ov["unit"] == "ST0001" and ov["attack_tickets"] == 3
    assert [t["unit"] for t in ov["targets"]] == ["ST0002", "ST0003"]     # 우리 지역·미참여 지역은 빠진다
    assert ov["targets"][0]["damage"] == pytest.approx(144) and ov["targets"][0]["mods"] == ["underdog"]

    await attack_svc.attack(db, me, "ST0002")
    await db.flush()
    incoming = await region.feed(db, "ST0002")
    assert incoming[0]["type"] == "attack" and incoming[0]["dir"] == "in"
    assert incoming[0]["other"] == "가시" and incoming[0]["nickname"] is None    # 다른 지역 닉네임은 숨김
    outgoing = await region.feed(db, "ST0001")
    assert outgoing[0]["dir"] == "out" and outgoing[0]["other"] == "나시" and outgoing[0]["nickname"] == "공격자"


async def test_verification_grants_attack_ticket(db_session):
    db = db_session
    me = await _world(db, tickets=0)
    me.starter_done = True
    place = Place(source="test", source_id="p1", kind="recycle_point", lat=35.8, lng=127.1, region_code=UNITS[0][0])
    db.add(place)
    await db.flush()

    async def verify(i):
        v = Verification(user_id=me.id, place_id=place.id, lat=35.8, lng=127.1, accuracy=10, result="success",
                         idempotency_key=f"atk-test-{i}")
        db.add(v)
        await db.flush()
        return await actions.settle(db, me, place, v)

    out = await verify(1)                   # 배출 요일 정보가 없으면 언제나 배출 시간으로 본다
    assert out["attack_tickets"] == 1 and me.attack_tickets == 1
    assert out["tickets"] >= 2              # 레이드 도전권은 따로 그대로

    me.attack_tickets = 5                   # 보유 상한
    out = await verify(2)
    assert "attack_tickets" not in out and out["attack_tickets_full"] is True
    assert me.attack_tickets == 5

    out = await verify(3)
    out = await verify(4)                   # 하루 보상 3번이 지나면 공격권도 없다
    assert "attack_tickets" not in out and "attack_tickets_full" not in out


async def test_no_attack_ticket_outside_dump_time(db_session):
    db = db_session
    me = await _world(db, tickets=0)
    home = await db.get(Region, UNITS[0][0])
    t = now()
    # 지금이 배출 시간이 아닌 요일로만 채운다
    home.dump_weekdays = ",".join(str(d) for d in range(7) if not actions.is_dump_time(
        Region(dump_weekdays=str(d)), t))
    assert not actions.is_dump_time(home, t)
    place = Place(source="test", source_id="p2", kind="recycle_point", lat=35.8, lng=127.1, region_code=home.code)
    db.add(place)
    await db.flush()
    v = Verification(user_id=me.id, place_id=place.id, lat=35.8, lng=127.1, accuracy=10, result="success",
                     idempotency_key="atk-test-x")
    db.add(v)
    await db.flush()
    out = await actions.settle(db, me, place, v)
    assert "attack_tickets" not in out and me.attack_tickets == 0
