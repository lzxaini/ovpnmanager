from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    """Return timezone-aware datetime in Asia/Shanghai."""
    return datetime.now(tz=SHANGHAI_TZ)


def now_shanghai_naive() -> datetime:
    """Return naive datetime representing Asia/Shanghai local time (for DB storage without tz)."""
    return now_shanghai().replace(tzinfo=None)
