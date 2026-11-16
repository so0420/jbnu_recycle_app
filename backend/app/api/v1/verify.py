import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.places import place_view
from app.api.v1.scan import refund_ai, reserve_ai
from app.core import auth
from app.core.config import settings
from app.core.security import limiter
from app.database import get_db
from app.models import Place, User, Verification
from app.services import images, locks
from app.services.ai import classifier
from app.services.clock import TZ, now
from app.services.game import actions

router = APIRouter()
OLD_PHOTO_MINUTES = 10
AI_BUDGET_S = 70          # Cloudflare(100초)보다 먼저 끝내고 결과를 돌려준다


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
                 taken_ms: int | None = Form(None),
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
        img = await asyncio.to_thread(images.open_image, raw)     # 이미지 처리는 이벤트 루프 밖에서
    except images.BadImage:
        raise HTTPException(400, "사진을 읽을 수 없어요. 다시 찍어 주세요")
    ph = await asyncio.to_thread(images.phash, img)
    taken = images.exif_taken_at(raw)
    if taken is None and taken_ms and 0 < taken_ms < 4_102_444_800_000:
        # 앱이 사진을 다시 저장하면서 EXIF 가 빠지므로, 기기가 알려 준 파일 시각을 대신 쓴다
        try:
            taken = datetime.fromtimestamp(taken_ms / 1000, TZ).replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            taken = None
    uid = user.id

    def new_v() -> Verification:
        return Verification(user_id=uid, lat=lat, lng=lng, accuracy=accuracy, result="fail",
                            idempotency_key=idempotency_key, phash=ph, judged_by="none")

    async def fail(v: Verification, code: str, message: str, detail: dict | None = None) -> dict:
        v.fail_code = code
        out = {"result": "fail", "code": code, "message": message, "detail": detail or {}}
        v.reward_json = out
        db.add(v)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        return out

    # ── 1단계: 위치·중복 확인 (짧은 트랜잭션) ──
    v = new_v()
    user = await locks.lock_user(db, user)
    try:
        cands = await actions.check_location(db, lat, lng, accuracy)
    except actions.VerifyFail as e:
        return await fail(v, e.code, e.message, e.detail)
    cand_ids = [p.id for p, _ in cands]
    picked = await actions.pick_place(db, user, cands)
    place, dist = picked or cands[0]
    v.place_id, v.distance_m = place.id, round(dist, 1)
    if taken and abs(now() - taken) > timedelta(minutes=OLD_PHOTO_MINUTES):
        return await fail(v, "OLD_PHOTO", "방금 찍은 사진으로 인증해 주세요")
    if picked is None:
        return await fail(v, "PLACE_ALREADY_TODAY", "이 수거장은 오늘 이미 인증했어요. 내일 다시 와 주세요")
    if await actions.duplicate_photo(db, user, place, ph):
        return await fail(v, "DUPLICATE_PHOTO", "이미 쓴 사진이에요. 새로 찍어 주세요")
    place_id = place.id
    await db.rollback()
    await reserve_ai(db, user)

    # ── 2단계: AI 판정 (잠금 없이, 전체 시간 제한) ──
    b64 = await asyncio.to_thread(images.to_b64_jpeg, img, settings.AI_IMAGE_EDGE)
    try:
        async with asyncio.timeout(AI_BUDGET_S):
            judge = await classifier.judge_disposal(db, b64)
    except TimeoutError:
        judge = classifier.VerifyJudge.busy()
    if judge.unavailable:
        await refund_ai(db, user)
        return await fail(_with_place(new_v(), place_id, dist), "AI_BUSY",
                          "AI가 지금 바빠요. 잠시 뒤 다시 인증해 주세요")
    if not judge.passed:
        v = _with_place(new_v(), place_id, dist)
        v.judged_by, v.score = judge.judged_by, judge.score
        return await fail(v, "NOT_RECYCLING_PHOTO",
                          "분리배출하는 모습이 보이게 찍어 주세요 (수거함과 버리는 물건이 함께 나오게)")

    # ── 3단계: 잠금 후 다시 확인하고 보상 (동시 요청 방지) ──
    user = await locks.lock_user(db, user)
    place = await db.get(Place, place_id)
    if await actions.place_done_today(db, user, place):     # 그새 다른 요청이 이 수거장을 썼으면 옆 수거함으로
        others = [(p, d) for p, d in cands if p.id in cand_ids and p.id != place_id]
        alt = await actions.pick_place(db, user, others)
        if alt is not None:
            place, dist = alt
            place_id = place.id
    v = _with_place(new_v(), place_id, dist)
    v.judged_by, v.score = judge.judged_by, judge.score
    if await actions.place_done_today(db, user, place):
        return await fail(v, "PLACE_ALREADY_TODAY", "이 수거장은 오늘 이미 인증했어요. 내일 다시 와 주세요")
    if await actions.duplicate_photo(db, user, place, ph):
        return await fail(v, "DUPLICATE_PHOTO", "이미 쓴 사진이에요. 새로 찍어 주세요")
    v.photo_path = await asyncio.to_thread(images.save, img, "verify")
    try:
        v.result = "success"
        reasons = [r for r in [actions.suspicious_speed(user, lat, lng),
                               "AI 판단 보류" if judge.uncertain else None,
                               "촬영 시각 정보 없음" if taken is None else None] if r]
        v.flagged = bool(reasons)
        v.flag_reason = ", ".join(reasons) or None
        db.add(v)
        await db.flush()
        reward = await actions.settle(db, user, place, v)
        user.last_lat, user.last_lng, user.last_verified_at = lat, lng, now()
        out = {"result": "success", "judged_by": judge.judged_by, "place": place_view(place, dist), "reward": reward}
        v.reward_json = out
        await db.commit()
    except IntegrityError:
        await db.rollback()
        images.remove(v.photo_path)
        raise HTTPException(409, "같은 요청이 이미 처리됐어요")
    except Exception:
        images.remove(v.photo_path)
        raise
    return out


def _with_place(v: Verification, place_id: int, dist: float) -> Verification:
    v.place_id, v.distance_m = place_id, round(dist, 1)
    return v
