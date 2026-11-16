"""모든 시간 판정은 서버 시각(KST) 기준."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

TZ = ZoneInfo(settings.TIMEZONE)


def now() -> datetime:
    """KST 기준 naive datetime (DB 저장용)."""
    return datetime.now(TZ).replace(tzinfo=None)


def today() -> date:
    return now().date()


def week_start(d: date | None = None) -> date:
    d = d or today()
    return d - timedelta(days=d.weekday())
