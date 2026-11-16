from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.config import settings
from app.core.security import limiter
from app.database import get_db
from app.models import User, Verification
from app.services import images
from app.services.ai import classifier
from app.services.clock import now
from app.services.game import actions, economy
from app.api.v1.places import place_view

router = APIRouter()


@router.get("/verify/nearest")
async def nearest(lat: float, lng: float, accuracy: float = 30, db: AsyncSession = Depends(get_db)):
    """인증 화면: 가장 가까운 수거장과 인증 가능 여부 미리 보기."""
    rows = await actions.nearby_places(db, lat, lng, 500, actions.DISPOSAL_KINDS, limit=5)
    rows = [(p, d) for p, d in rows if p.is_active]
    limit = max(settings.VERIFY_RADIUS_M, min(accuracy, settings.VERIFY_MAX_ACCURACY_M))
    return {"limit_m": round(limit), "accuracy_ok": accuracy <= settings.VERIFY_MAX_ACCURACY_M,
            "places": [place_view(p, d) | {"in_range": d <= limit} for p, d in rows]}


@router.post("/verify")
@limiter.limit("6/minute")
async def verify(request: Request, photo: UploadFile = File(...), lat: float = Form(...), lng: float = Form(...),
                 accuracy: float = Form(...), idempotency_key: str = Form(..., min_length=8, max_length=64),
                 user: User = Depends(auth.current_user), db: AsyncSession = Depends(get_db)):
    old = (await db.execute(select(Verification).where(Verification.idempotency_key == idempotency_key))).scalars().first()
    if old:
        if old.user_id != user.id:
            raise HTTPException(409, "다시 시도해 주세요")
        return old.reward_json or {"result": old.result, "code": old.fail_code}
    if not user.starter_done:
        raise HTTPException(400, "먼저 첫 리몬을 골라 주세요")

    raw = await photo.read()
    try:
        img = images.open_image(raw)
    except images.BadImage:
        raise HTTPException(400, "사진을 읽을 수 없어요. 다시 찍어 주세요")
    taken = images.exif_taken_at(raw)
    ph = images.phash(img)
    v = Verification(user_id=user.id, lat=lat, lng=lng, accuracy=accuracy, result="fail",
                     idempotency_key=idempotency_key, phash=ph, judged_by="none")

    async def fail(code: str, message: str, detail: dict | None = None) -> dict:
        v.fail_code = code
        out = {"result": "fail", "code": code, "message": message, "detail": detail or {}}
        v.reward_json = out
        db.add(v)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        return out

    try:
        place, dist = await actions.check_location(db, lat, lng, accuracy)
    except actions.VerifyFail as e:
        return await fail(e.code, e.message, e.detail)
    v.place_id, v.distance_m = place.id, round(dist, 1)

    if taken and abs(now() - taken) > timedelta(minutes=10):
        return await fail("OLD_PHOTO", "방금 찍은 사진으로 인증해 주세요")
    if await actions.place_done_today(db, user, place):
        return await fail("PLACE_ALREADY_TODAY", "이 수거장은 오늘 이미 인증했어요. 내일 다시 와 주세요")
    if await actions.duplicate_photo(db, user, place, ph):
        return await fail("DUPLICATE_PHOTO", "이미 쓴 사진이에요. 새로 찍어 주세요")

    judge = await classifier.judge_disposal(db, images.to_b64_jpeg(img, settings.AI_IMAGE_EDGE))
    v.judged_by, v.score = judge.judged_by, judge.score
    if not judge.passed:
        return await fail("NOT_RECYCLING_PHOTO", "분리배출하는 모습이 보이게 찍어 주세요 (수거함과 버리는 물건이 함께 나오게)")

    v.photo_path = images.save(img, "verify")
    v.result = "success"
    reasons = [r for r in [actions.suspicious_speed(user, lat, lng), "AI 판단 보류" if judge.uncertain else None] if r]
    v.flagged = bool(reasons)
    v.flag_reason = ", ".join(reasons) or None
    db.add(v)
    await db.flush()
    reward = await actions.settle(db, user, place, v)
    user.last_lat, user.last_lng, user.last_verified_at = lat, lng, now()
    out = {"result": "success", "judged_by": judge.judged_by,
           "place": place_view(place, dist), "reward": reward}
    v.reward_json = out
    await db.commit()
    return out


_ = economy
