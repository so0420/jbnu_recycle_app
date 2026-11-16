"""앱 안의 간단한 주기 작업: 자정 청결도 감소, 30일 지난 사진·좌표 삭제, 오래된 전투 기록 정리."""
import asyncio
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models import ClassifyLog, JobLog, RaidAttempt, Verification
from app.services.clock import now, today
from app.services.game import region
from app.utils.log import logger

RETENTION_DAYS = 30


async def _once(name: str, key: str) -> bool:
    """오늘 이 작업을 처음 실행하면 True (여러 워커가 있어도 한 번만)."""
    async with AsyncSessionLocal() as db:
        db.add(JobLog(name=name, key=key))
        try:
            await db.commit()
            return True
        except IntegrityError:
            return False


async def daily_jobs() -> None:
    key = today().isoformat()
    if await _once("daily_decay", key):
        async with AsyncSessionLocal() as db:
            await region.daily_decay(db)
            await db.commit()
        logger.info("자정 작업: 청결도 감소 완료")
    if await _once("retention", key):
        cutoff = now() - timedelta(days=RETENTION_DAYS)
        async with AsyncSessionLocal() as db:
            for model in (ClassifyLog, Verification):
                rows = (await db.execute(select(model.id, model.photo_path).where(
                    model.created_at < cutoff, model.photo_path != ""))).all()
                for _, p in rows:
                    Path(settings.UPLOAD_DIR, p).unlink(missing_ok=True)
                await db.execute(update(model).where(model.created_at < cutoff, model.photo_path != "")
                                 .values(photo_path=""))
            await db.execute(update(Verification).where(Verification.created_at < cutoff, Verification.lat != 0)
                             .values(lat=0, lng=0))
            await db.execute(update(RaidAttempt).where(RaidAttempt.created_at < now() - timedelta(days=7))
                             .values(log_json=None))
            await db.commit()
        logger.info("자정 작업: 보관 기간 지난 사진·위치 삭제 완료")


async def loop() -> None:
    while True:
        try:
            await daily_jobs()
        except Exception as e:  # 스케줄러가 죽지 않게
            logger.error(f"주기 작업 실패: {e!r}")
        await asyncio.sleep(60)
