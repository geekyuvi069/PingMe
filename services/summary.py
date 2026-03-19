import pytz
from datetime import datetime, timezone, timedelta

PING_INTERVAL_MINUTES = 15

async def get_today_range(db):
    """
    Returns (start_utc, end_utc, date_str, user_tz) for the user's local day.
    """
    settings = await db.settings.find_one({"userId": "default"})
    tz_str = settings.get("timezone", "Asia/Kolkata") if settings else "Asia/Kolkata"
    user_tz = pytz.timezone(tz_str)
    
    now_local = datetime.now(user_tz)
    local_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = local_start.astimezone(pytz.utc)
    today_end_utc = today_start_utc + timedelta(days=1)
    today_str = now_local.strftime("%Y-%m-%d")
    
    return today_start_utc, today_end_utc, today_str, user_tz

def format_duration(minutes: float) -> str:
    minutes = int(minutes)
    if minutes <= 0:
        return "0m"
    h = minutes // 60
    m = minutes % 60
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    elif h > 0:
        return f"{h}h"
    else:
        return f"{m}m"

def compute_stats(logs, agenda, interval_minutes=PING_INTERVAL_MINUTES):
    category_minutes = {}
    active_minutes = 0

    for log in logs:
        if log.get("skipped") or log.get("untracked"):
            continue
        cat = log.get("category", "untracked")
        category_minutes[cat] = category_minutes.get(cat, 0) + interval_minutes
        active_minutes += interval_minutes

    untracked_count = sum(1 for l in logs if l.get("untracked") or l.get("skipped"))

    return {
        "active_minutes": active_minutes,
        "study_minutes": category_minutes.get("deep_work", 0),
        "break_minutes": category_minutes.get("break", 0),
        "admin_minutes": category_minutes.get("admin", 0),
        "meetings_minutes": category_minutes.get("meetings", 0),
        "distracted_minutes": category_minutes.get("distracted", 0),
        "untracked_minutes": untracked_count * interval_minutes,
        "untracked_count": untracked_count,
        "total_pings": len(logs),
        "agenda_total": len(agenda),
        "agenda_completed": sum(1 for i in agenda if i.get("completed")),
        "category_minutes": category_minutes,
    }
