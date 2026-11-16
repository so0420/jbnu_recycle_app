"""API 흐름 점검: 가입 → 스타터 → 스캔 → 인증 → 캡슐 → 레벨업 → 레이드.

사용: python scripts/smoke_test.py http://127.0.0.1:11000 [사진.jpg]
테스트 계정을 새로 만든다 (smoke_<랜덤>).
"""
import io
import json
import random
import sys
import uuid

import httpx
from PIL import Image

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:11000"
PHOTO = sys.argv[2] if len(sys.argv) > 2 else None


def jpeg() -> bytes:
    if PHOTO:
        return open(PHOTO, "rb").read()
    im = Image.new("RGB", (640, 640), (random.randint(0, 255), 200, 220))
    b = io.BytesIO()
    im.save(b, "JPEG")
    return b.getvalue()


def show(name, r):
    try:
        body = r.json()
    except ValueError:
        body = r.text[:200]
    s = json.dumps(body, ensure_ascii=False)
    print(f"[{r.status_code}] {name}: {s[:400]}")
    return body


def main():
    c = httpx.Client(base_url=BASE, timeout=120)
    show("health", c.get("/health"))
    regions = c.get("/api/v1/regions/list").json()
    code = next(r["code"] for r in regions if r["name"] == "덕진동")
    lid = f"smoke_{uuid.uuid4().hex[:6]}"
    show("signup", c.post("/api/v1/auth/signup", json={"login_id": lid, "password": "test1234", "nickname": lid[-8:],
                                                        "region_code": code, "agree_terms": True, "agree_privacy": True}))
    show("me", c.get("/api/v1/me"))
    show("starter", c.post("/api/v1/monsters/starter", json={"species": "candol"}))
    show("scan", c.post("/api/v1/scan", files={"photo": ("a.jpg", jpeg(), "image/jpeg")}))
    show("bag", c.get("/api/v1/bag"))
    # 덕진동 재활용 동네마당 (4146) 좌표 근처
    near = show("nearest", c.get("/api/v1/verify/nearest", params={"lat": 35.8586578, "lng": 127.1443953, "accuracy": 20}))
    p = near["places"][0]
    show("verify", c.post("/api/v1/verify", data={"lat": p["lat"] + 0.0001, "lng": p["lng"], "accuracy": 15,
                                                   "idempotency_key": uuid.uuid4().hex},
                          files={"photo": ("v.jpg", jpeg(), "image/jpeg")}))
    show("verify too far", c.post("/api/v1/verify", data={"lat": 35.80, "lng": 127.10, "accuracy": 15,
                                                           "idempotency_key": uuid.uuid4().hex},
                                  files={"photo": ("v.jpg", jpeg(), "image/jpeg")}))
    caps = show("capsules", c.get("/api/v1/capsules"))
    for cap in caps:
        show("open", c.post(f"/api/v1/capsules/{cap['id']}/open"))
    mons = show("monsters", c.get("/api/v1/monsters"))["monsters"]
    show("levelup", c.post(f"/api/v1/monsters/{mons[0]['id']}/levelup"))
    show("party", c.put("/api/v1/party", json={"ids": [m["id"] for m in mons[:3]] + [None] * (3 - len(mons[:3])),
                                               "timings": {}}))
    show("missions", c.get("/api/v1/missions"))
    show("raid", c.get("/api/v1/raid"))
    show("raid attempt (잠김 예상)", c.post("/api/v1/raid/attempt"))
    show("regions", c.get("/api/v1/regions"))
    show("dex", c.get("/api/v1/dex"))
    show("me after", c.get("/api/v1/me"))


if __name__ == "__main__":
    main()
