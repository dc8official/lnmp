from __future__ import annotations
import datetime

def get_local_timezone() -> datetime.tzinfo:
    """Retrieve the current local operating system timezone."""
    # datetime.now().astimezone() returns a timezone-aware object for the OS local zone
    tz = datetime.datetime.now().astimezone().tzinfo
    if tz is None:
        # Fallback in case of unexpected timezone configurations
        return datetime.timezone.utc
    return tz

def localize_datetime(dt: datetime.datetime) -> datetime.datetime:
    """Convert a datetime object to be timezone-aware in the local OS timezone."""
    local_tz = get_local_timezone()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=local_tz)
    return dt.astimezone(local_tz)
