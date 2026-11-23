"""요일별 배출 품목 (전주 단독주택·상가: 일·화 또는 월·수, 앞 요일 = 플라스틱·병·금속, 뒤 요일 = 투명페트·비닐·종이)."""
from datetime import datetime

from app.models import Region
from app.services.game import actions

ROUND1 = ["플라스틱", "병류", "금속류", "스티로폼"]
ROUND2 = ["투명페트병", "비닐류", "종이류", "스티로폼"]


def jj(weekdays: str, sgg: str = "52111") -> Region:
    return Region(code=sgg + "00000", name="테스트동", gu="전주시", sigungu_code=sgg, dump_weekdays=weekdays)


def test_schedule_days():
    s = actions.dump_schedule(jj("1,3"))
    assert [d["weekday"] for d in s["days"]] == [1, 3]
    assert s["days"][0]["items"] == ROUND1 and s["days"][1]["items"] == ROUND2
    assert actions.dump_schedule(jj("2,0", "52113"))["days"][0] == {"weekday": 0, "items": ROUND1}   # 일·화
    assert actions.dump_schedule(jj("")) is None                    # 요일을 모르는 동
    assert actions.dump_schedule(jj("1,3", "11110")) is None        # 규칙이 없는 지역
    assert actions.dump_schedule(None) is None


def test_items_now_and_next():
    mon_wed = jj("1,3")
    # 2026-11-22 은 일요일
    assert actions.dump_items_for(mon_wed, datetime(2026, 11, 22, 19, 0)) == ROUND1   # 일 저녁 = 월요일 수거분
    assert actions.dump_items_for(mon_wed, datetime(2026, 11, 23, 3, 0)) == ROUND1    # 월 새벽
    assert actions.dump_items_for(mon_wed, datetime(2026, 11, 23, 10, 0)) == ROUND2   # 다음은 화 저녁 → 수요일 수거
    assert actions.dump_items_for(mon_wed, datetime(2026, 11, 25, 12, 0)) == ROUND1   # 수 낮 → 다음 주 월요일
    sun_tue = jj("0,2")
    assert actions.dump_items_for(sun_tue, datetime(2026, 11, 21, 20, 0)) == ROUND1   # 토 저녁 = 일요일 수거분
    assert actions.dump_items_for(sun_tue, datetime(2026, 11, 23, 18, 30)) == ROUND2  # 월 저녁 = 화요일 수거분
    assert actions.dump_items_for(jj(""), datetime(2026, 11, 23, 18, 30)) is None


def test_dump_when_by_category():
    r = jj("1,3")
    assert actions.dump_when(r, "pet_clear") == [3]
    assert actions.dump_when(r, "can") == [1]
    assert actions.dump_when(r, "styrofoam") == [1, 3]
    assert actions.dump_when(r, "battery") is None        # 요일제 품목이 아님 (전용 수거함)
    assert actions.dump_when(r, None) is None
    assert actions.dump_when(jj(""), "can") is None
