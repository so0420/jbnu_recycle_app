from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.config import settings
from app.core.security import limiter
from app.database import get_db
from app.models import ClassifyLog, User
from app.services import images
from app.services.ai import classifier
from app.services.game import actions, data, economy

router = APIRouter()
AI_DAILY_LIMIT = 30


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


@router.post("/scan")
@limiter.limit("10/minute")
async def scan(request: Request, photo: UploadFile = File(...), user: User = Depends(auth.current_user),
               db: AsyncSession = Depends(get_db)):
    d = await economy.daily(db, user)
    if d.ai_calls >= AI_DAILY_LIMIT:
        raise HTTPException(429, f"오늘은 사진 분석을 {AI_DAILY_LIMIT}번까지 할 수 있어요")
    raw = await photo.read()
    try:
        img = images.open_image(raw)
    except images.BadImage:
        raise HTTPException(400, "사진을 읽을 수 없어요. 다시 찍어 주세요")
    d.ai_calls += 1
    ph = images.phash(img)
    path = images.save(img, "scan")
    res = await classifier.classify(db, images.to_b64_jpeg(img, settings.AI_IMAGE_EDGE))
    log = ClassifyLog(user_id=user.id, photo_path=path, phash=ph, s1_json=res.s1, s2_json=res.s2,
                      category=res.category, item_label=res.item_label, judged_by=res.judged_by, clean=res.clean,
                      habit_ok=res.habit_ok, latency_ms=res.latency_ms)
    db.add(log)
    await db.flush()
    reward = await actions.on_scan(db, user, res, log)
    await db.commit()
    return {"log_id": log.id, "result": res.as_dict(), "guide": guide_view(res.category, res.item_label),
            "candidates": [guide_view(c, None) for c in res.candidates] if res.needs_user_choice else [],
            "reward": reward}


class ChooseIn(BaseModel):
    category: str


@router.post("/scan/{log_id}/choose")
async def choose(log_id: int, body: ChooseIn, user: User = Depends(auth.current_user),
                 db: AsyncSession = Depends(get_db)):
    """AI 가 모를 때 사용자가 후보 중 고른다. 보상은 XP·도감만 (가방에는 담지 않음)."""
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
