import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.config import settings
from app.core.security import limiter
from app.database import get_db
from app.models import ClassifyLog, User
from app.services import images, locks
from app.services.ai import classifier
from app.services.game import actions, data, economy

router = APIRouter()
AI_DAILY_LIMIT = 40          # 스캔 + 인증 판정을 합친 하루 AI 사용 횟수
AI_BUDGET_S = 70             # Cloudflare(100초)보다 먼저 끝낸다


def guide_view(category: str | None, item_label: str | None) -> dict | None:
    if not category:
        return None
    g = data.guides()
    cat = g["categories"][category]
    item = data.items_by_label().get(item_label or "")
    if item is None:
        same = [it for it in g["items"] if it["category"] == category]
        item = same[0] if len(same) == 1 else None
    return {"category": category, "category_name": cat["name"], "type": cat["type"],
            "recyclable": cat["type"] != "none",
            "item": item, "habit_name": g["habits"].get(cat["type"], {}).get("name")}


async def reserve_ai(db: AsyncSession, user: User) -> None:
    """AI 사용 1회를 짧은 트랜잭션으로 먼저 예약한다 (동시 요청으로 한도를 넘지 못하게)."""
    user = await locks.lock_user(db, user)
    d = await economy.daily(db, user)
    if d.ai_calls >= AI_DAILY_LIMIT:
        await db.rollback()
        raise HTTPException(429, f"오늘은 사진 판정을 {AI_DAILY_LIMIT}번까지 할 수 있어요. 내일 다시 해 주세요")
    d.ai_calls += 1
    await db.commit()


async def refund_ai(db: AsyncSession, user: User) -> None:
    user = await locks.lock_user(db, user)
    d = await economy.daily(db, user)
    d.ai_calls = max(0, d.ai_calls - 1)
    await db.commit()


@router.post("/scan")
@limiter.limit("10/minute")
async def scan(request: Request, photo: UploadFile = File(...), user: User = Depends(auth.current_user),
               db: AsyncSession = Depends(get_db)):
    raw = await photo.read()
    try:
        img = await asyncio.to_thread(images.open_image, raw)     # 이미지 처리는 이벤트 루프 밖에서
    except images.BadImage:
        raise HTTPException(400, "사진을 읽을 수 없어요. 다시 찍어 주세요")
    await reserve_ai(db, user)
    # AI 판정 동안에는 DB 잠금·트랜잭션을 잡고 있지 않는다
    b64 = await asyncio.to_thread(images.to_b64_jpeg, img, settings.AI_IMAGE_EDGE)
    try:
        async with asyncio.timeout(AI_BUDGET_S):
            res = await classifier.classify(db, b64)
    except TimeoutError:
        res = None
    if res is None or res.raw is None:
        await refund_ai(db, user)
        raise HTTPException(409, "AI가 지금 바빠요. 잠시 뒤 다시 찍어 주세요")
    if res.category is None:
        # AI 가 확신이 없으면 사용자가 고르게: AI 가 짐작한 분류를 앞에, 일반쓰레기까지 전부
        cats = list(data.guides()["categories"])
        guess = res.candidates[0] if res.candidates else None
        res.candidates = ([guess] if guess in cats else []) + [c for c in cats if c != guess]
    ph = await asyncio.to_thread(images.phash, img)
    user = await locks.lock_user(db, user)
    path = await asyncio.to_thread(images.save, img, "scan")
    try:
        log = ClassifyLog(user_id=user.id, photo_path=path, phash=ph, s2_json=res.raw,
                          category=res.category, item_label=res.item_label, judged_by=res.judged_by,
                          clean=res.clean, habit_ok=res.habit_ok, latency_ms=res.latency_ms)
        db.add(log)
        await db.flush()
        reward = await actions.on_scan(db, user, res, log)
        await db.commit()
    except Exception:
        images.remove(path)
        raise
    return {"log_id": log.id, "result": res.as_dict(), "guide": guide_view(res.category, res.item_label),
            "candidates": [guide_view(c, None) for c in res.candidates] if res.needs_user_choice else [],
            "reward": reward}


class ChooseIn(BaseModel):
    category: str


@router.post("/scan/{log_id}/choose")
async def choose(log_id: int, body: ChooseIn, user: User = Depends(auth.current_user),
                 db: AsyncSession = Depends(get_db)):
    """AI 가 모를 때 사용자가 후보 중 고른다. 버리는 법만 알려 주고 보상은 없다 (가방·경험치 없음)."""
    log = await db.get(ClassifyLog, log_id)
    if log is None or log.user_id != user.id:
        raise HTTPException(404, "기록을 찾을 수 없어요")
    if body.category not in data.guides()["categories"]:
        raise HTTPException(400, "분류를 다시 골라 주세요")
    if log.category is None:
        log.category = body.category
        log.judged_by = "user"
    await db.commit()
    return {"guide": guide_view(body.category, None)}
