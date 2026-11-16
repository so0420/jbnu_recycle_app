from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.config import settings
from app.database import get_db
from app.models import AiUsage, ClassifyLog, User, Verification
from app.services.clock import now, today
from app.services.game import data

router = APIRouter()


@router.get("/stats")
async def stats(_: User = Depends(auth.admin_user), db: AsyncSession = Depends(get_db)):
    since = now() - timedelta(days=7)
    total_scans = (await db.execute(select(func.count()).select_from(ClassifyLog)
                                    .where(ClassifyLog.created_at >= since))).scalar_one()
    by = dict((await db.execute(select(ClassifyLog.judged_by, func.count()).where(ClassifyLog.created_at >= since)
                                .group_by(ClassifyLog.judged_by))).all())
    lat = (await db.execute(select(func.avg(ClassifyLog.latency_ms)).where(ClassifyLog.created_at >= since))).scalar()
    ver = dict((await db.execute(select(Verification.result, func.count()).where(Verification.created_at >= since)
                                 .group_by(Verification.result))).all())
    fails = dict((await db.execute(select(Verification.fail_code, func.count()).where(
        Verification.created_at >= since, Verification.result == "fail").group_by(Verification.fail_code))).all())
    users = (await db.execute(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))).scalar_one()
    usage = await db.get(AiUsage, (today(), "openai"))
    return {"users": users, "scans_7d": total_scans, "judged_by_7d": by,
            "system_one_ratio": round(by.get("system_one", 0) / total_scans, 3) if total_scans else None,
            "avg_latency_ms": round(lat or 0), "verifications_7d": ver, "fail_codes_7d": fails,
            "openai_tokens_today": usage.tokens if usage else 0,
            "openai_daily_limit": settings.OPENAI_DAILY_TOKEN_LIMIT}


@router.get("/verifications")
async def flagged(only_flagged: bool = True, _: User = Depends(auth.admin_user), db: AsyncSession = Depends(get_db)):
    q = select(Verification).order_by(Verification.id.desc()).limit(100)
    if only_flagged:
        q = q.where(Verification.flagged.is_(True))
    rows = (await db.execute(q)).scalars()
    return [{"id": v.id, "user_id": v.user_id, "at": v.created_at.isoformat(), "result": v.result,
             "fail_code": v.fail_code, "flag_reason": v.flag_reason, "score": v.score, "judged_by": v.judged_by,
             "place_id": v.place_id, "distance_m": v.distance_m, "has_photo": bool(v.photo_path)} for v in rows]


@router.post("/verifications/{vid}/clear")
async def clear_flag(vid: int, _: User = Depends(auth.admin_user), db: AsyncSession = Depends(get_db)):
    v = await db.get(Verification, vid)
    if v is None:
        raise HTTPException(404)
    v.flagged = False
    await db.commit()
    return {"ok": True}


@router.get("/photo/{kind}/{vid}")
async def photo(kind: str, vid: int, _: User = Depends(auth.admin_user), db: AsyncSession = Depends(get_db)):
    obj = await db.get(Verification if kind == "verify" else ClassifyLog, vid)
    if obj is None or not obj.photo_path:
        raise HTTPException(404)
    p = Path(settings.UPLOAD_DIR) / obj.photo_path
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@router.post("/reload-game-data")
async def reload_data(_: User = Depends(auth.admin_user)):
    data.reload_all()
    return {"ok": True}
