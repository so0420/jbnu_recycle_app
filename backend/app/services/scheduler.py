"""앱 안의 간단한 주기 작업.

- 자정: 지역 청결도 감소
- 보관 기간(30일) 지난 사진·위치 삭제, 남은 사진 파일 정리, 30일 지난 로그 파일 삭제
- 7일 지난 전투 기록 정리
작업은 하루 한 번만 실행하고(job_log), 실패하면 기록을 지워 다음 주기에 다시 시도한다.
"""
import asyncio
import os
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models import ClassifyLog, JobLog, RaidAttempt, User, Verification
from app.services.clock import now, today
from app.services.game import region
from app.utils.log import LOG_DIR, logger

RETENTION_DAYS = 30


async def _claim(name: str, key: str) -> bool:
    async with AsyncSessionLocal() as db:
        db.add(JobLog(name=name, key=key))
        try:
            await db.commit()
            return True
        except IntegrityError:
            return False


async def _release(name: str, key: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(JobLog).where(JobLog.name == name, JobLog.key == key))
        await db.commit()


async def _run_once(name: str, key: str, fn) -> None:
    if not await _claim(name, key):
        return
    try:
        await fn()
        logger.info(f"주기 작업 완료: {name}")
    except Exception as e:
        logger.error(f"주기 작업 실패, 다음에 다시 시도: {name} {e!r}")
        await _release(name, key)


async def _decay() -> None:
    async with AsyncSessionLocal() as db:
        await region.daily_decay(db)
        await db.commit()


def _sweep_dir(root: Path, max_age_days: int, pattern: str = "*") -> int:
    """mtime 기준으로 오래된 파일 삭제 (DB 에 기록되지 않은 사진 파일까지 정리)."""
    if not root.is_dir():
        return 0
    cutoff = time.time() - max_age_days * 86400
    n = 0
    for f in root.rglob(pattern):
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                n += 1
        except OSError:
            pass
    return n


async def _retention() -> None:
    cutoff = now() - timedelta(days=RETENTION_DAYS)
    async with AsyncSessionLocal() as db:
        for model in (ClassifyLog, Verification):
            rows = (await db.execute(select(model.photo_path).where(
                model.created_at < cutoff, model.photo_path != ""))).scalars().all()
            for p in rows:
                Path(settings.UPLOAD_DIR, p).unlink(missing_ok=True)
            await db.execute(update(model).where(model.created_at < cutoff, model.photo_path != "")
                             .values(photo_path=""))
        await db.execute(update(Verification).where(Verification.created_at < cutoff,
                                                    (Verification.lat != 0) | (Verification.accuracy != 0)
                                                    | Verification.distance_m.is_not(None)
                                                    | Verification.reward_json.is_not(None))
                         .values(lat=0, lng=0, accuracy=0, distance_m=None, reward_json=None))
        await db.execute(update(User).where(User.last_verified_at < cutoff, User.last_lat.is_not(None))
                         .values(last_lat=None, last_lng=None))
        await db.execute(update(RaidAttempt).where(RaidAttempt.created_at < now() - timedelta(days=7))
                         .values(log_json=None))
        await db.commit()
    n_photo = _sweep_dir(Path(settings.UPLOAD_DIR), RETENTION_DAYS, "*.jpg")
    n_log = _sweep_dir(Path(LOG_DIR), RETENTION_DAYS, "*.log*")
    logger.info(f"보관 기간 정리: 남은 사진 파일 {n_photo}개, 로그 파일 {n_log}개 삭제")


async def daily_jobs() -> None:
    key = today().isoformat()
    await _run_once("daily_decay", key, _decay)
    await _run_once("retention", key, _retention)


async def loop() -> None:
    from app.services.game import raid
    n = 0
    while True:
        try:
            await daily_jobs()
            if n % 10 == 0:                       # 10분마다: 지급이 끝나지 않은 레이드 처치 보상 이어서
                await raid.retry_pending_kills()
        except Exception as e:  # 스케줄러가 죽지 않게
            logger.error(f"주기 작업 실패: {e!r}")
        n += 1
        await asyncio.sleep(60)


_ = os
