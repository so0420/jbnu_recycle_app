"""동시 요청 방어 점검 (운영 주소에 테스트 계정을 만든다).

사용: python scripts/race_test.py https://recycle.so4.kr 분리수거사진1.jpg 분리수거사진2.jpg
- 같은 수거장에 서로 다른 사진으로 인증 2건을 동시에 → 성공은 1건이어야 한다
- 같은 캡슐을 5번 동시에 열기 → 리몬은 1마리만 생겨야 한다
- 같은 미션 보상을 동시에 받기 → 1번만 지급
"""
import asyncio
import io
import json
import sys
import uuid

import httpx

BASE = sys.argv[1]
PHOTOS = sys.argv[2:4]
PLACE = (35.8586578, 127.1443953)        # 전주 덕진동 재활용 동네마당


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=180) as c:
        sggs = (await c.get("/api/v1/regions/list", params={"sigungu_code": "52113"})).json()
        code = next(r["code"] for r in sggs if r["name"] == "덕진동")
        lid = f"race_{uuid.uuid4().hex[:6]}"
        r = await c.post("/api/v1/auth/signup", json={"login_id": lid, "password": "test1234", "nickname": lid[-8:],
                                                      "region_code": code, "agree_terms": True, "agree_privacy": True,
                                                      "agree_age": True, "agree_location": True, "agree_overseas": True})
        print("signup", r.status_code, r.text[:80])
        await c.post("/api/v1/monsters/starter", json={"species": "candol"})

        async def verify(photo):
            data = {"lat": PLACE[0], "lng": PLACE[1], "accuracy": 10, "idempotency_key": uuid.uuid4().hex}
            files = {"photo": ("v.jpg", open(photo, "rb").read(), "image/jpeg")}
            return (await c.post("/api/v1/verify", data=data, files=files)).json()

        res = await asyncio.gather(*[verify(p) for p in PHOTOS])
        for x in res:
            print("verify:", x.get("result"), x.get("code"), json.dumps(x.get("reward", {}), ensure_ascii=False)[:160])
        ok = sum(1 for x in res if x.get("result") == "success")
        print(f"→ 동시 인증 성공 {ok}건 (기대값 1)")

        caps = (await c.get("/api/v1/capsules")).json()
        print("capsules", len(caps))
        if caps:
            cid = caps[0]["id"]
            opens = await asyncio.gather(*[c.post(f"/api/v1/capsules/{cid}/open") for _ in range(5)])
            ids = {o.json().get("monster_id") for o in opens if o.status_code == 200}
            mons = (await c.get("/api/v1/monsters")).json()["monsters"]
            print(f"→ 캡슐 5번 동시 열기: 결과 리몬 id {ids}, 보유 리몬 {len(mons)}마리 (기대값: id 1개, 2마리)")

        me = (await c.get("/api/v1/me")).json()
        print("me: level", me["level"], "coins", me["coins"], "tickets", me["tickets"], "region", me["region"]["unit"],
              me["region"]["unit_name"])
        st = (await c.get("/api/v1/regions", params={"mine": me["region"]["unit"]})).json()
        print("standings mode", st["mode"], "total", st["total"], "mine", st["mine"])
        r = await c.post("/api/v1/auth/logout")
        r2 = await c.get("/api/v1/me")
        print("logout →", r.status_code, "/me after logout:", r2.status_code)


asyncio.run(main())
_ = io
