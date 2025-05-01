# app/utils/time_utils.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytz
import tzlocal  

# Detect your server’s local time-zone once at import time:
LOCAL_TZ = tzlocal.get_localzone()           # e.g. Asia/Kolkata
UTC     = pytz.UTC                           

def to_utc_iso(dt: datetime) -> str:
    """Convert any aware datetime to UTC ISO string ending in Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def now_utc_iso() -> str:
    return to_utc_iso(datetime.now(UTC))

def epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)

def now_utc() -> datetime:
    """Current UTC time, timezone-aware."""
    return datetime.now(UTC)

def now_local() -> datetime:
    """Current local time (as per server OS settings), timezone-aware."""
    return now_utc().astimezone(LOCAL_TZ)

def to_local(dt: datetime) -> datetime:
    """
    Convert any timezone-aware datetime to LOCAL_TZ.
    If dt is naive, assume UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(LOCAL_TZ)

def to_utc(dt: datetime) -> datetime:
    """
    Convert any timezone-aware datetime to UTC.
    If dt is naive, assume LOCAL_TZ.
    """
    if dt.tzinfo is None:
        # zoneinfo.ZoneInfo doesn't have .localize, so attach tzinfo directly
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC)

def format_iso(dt: datetime, tz: str = "utc") -> str:
    """
    Produce an ISO string. tz may be "utc" or "local".
    """
    if tz == "local":
        dt = to_local(dt)
    else:
        dt = to_utc(dt)
    return dt.isoformat()

def parse_iso(s: str) -> datetime:
    """
    Parse any ISO string with or without offset into an aware datetime.
    Accepts trailing 'Z' (Zulu) by converting it to '+00:00'.
    """
    # support "YYYY-MM-DDThh:mm:ssZ"
    if s.endswith("Z") and not s.endswith("+00:00"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # assume UTC if no offset
        return dt.replace(tzinfo=UTC)
    return dt
