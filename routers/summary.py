import os
import pytz
from fastapi import APIRouter, Depends, Header, HTTPException
from services.db import get_db
from services.ai import generate_ai_summary
from services.summary import compute_stats, format_duration, get_today_range
from routers.reading import get_reading_stats
from services.email_template import generate_html_email
from datetime import datetime, timezone, timedelta
from services.email import send_email

router = APIRouter(prefix="/api/summary", tags=["summary"])

CRON_SECRET = os.getenv("CRON_SECRET")
PING_INTERVAL_MINUTES = 15




@router.get("/")
async def get_summary(db=Depends(get_db)):
    utc_start, utc_end, today_str, user_tz = await get_today_range(db)

    # Use range query to be precise
    query = {"timestamp": {"$gte": utc_start, "$lt": utc_end}}
    logs = await db.logs.find(query).sort("timestamp", 1).to_list(200)
    notes = await db.notes.find(query).sort("timestamp", 1).to_list(100)
    agenda = await db.agenda.find({"date": today_str}).to_list(100)

    stats = compute_stats(logs, agenda)
    reading = await get_reading_stats(db)

    # Convert timestamps to local time for JSON output
    for item in logs + notes + agenda:
        item["_id"] = str(item["_id"])
        for field in ["timestamp", "completedAt", "createdAt"]:
            if field in item and isinstance(item[field], datetime):
                dt = item[field]
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                item[field] = dt.astimezone(user_tz).isoformat()

    return {
        "date": today_str,
        "logs": logs,
        "notes": notes,
        "agenda": agenda,
        "reading": reading,
        "stats": {
            "totalPings": stats["total_pings"],
            "trackedCount": stats["total_pings"] - stats["untracked_count"],
            "untrackedCount": stats["untracked_count"],
            "untrackedPercent": int(stats["untracked_count"] / stats["total_pings"] * 100) if stats["total_pings"] > 0 else 0,
            "categoryBreakdown": stats["category_minutes"],
            "activeMinutes": stats["active_minutes"],
            "studyMinutes": stats["study_minutes"],
            "agendaCompleted": stats["agenda_completed"],
            "agendaTotal": stats["agenda_total"],
        }
    }


@router.post("/send")
@router.post("/send/")
async def send_summary(x_cron_secret: str = Header(None), db=Depends(get_db)):
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    utc_start, utc_end, today_str, user_tz = await get_today_range(db)

    # 1. Fetch data
    query = {"timestamp": {"$gte": utc_start, "$lt": utc_end}}
    logs = await db.logs.find(query).sort("timestamp", 1).to_list(200)
    notes = await db.notes.find(query).sort("timestamp", 1).to_list(100)
    agenda = await db.agenda.find({"date": today_str}).to_list(100)

    # 2. Compute stats
    stats = compute_stats(logs, agenda)
    reading = await get_reading_stats(db)

    # 3. Generate AI Insight (Gemini)
    ai_insight = await generate_ai_summary(logs, agenda, notes, stats)

    # 4. Save Daily Snapshot (Consolidated)
    snapshot = {
        "date": today_str,
        "study_minutes": stats["study_minutes"],
        "active_minutes": stats["active_minutes"],
        "agenda_completed": stats["agenda_completed"],
        "agenda_total": stats["agenda_total"],
        "total_pings": stats["total_pings"],
        "untracked_count": stats["untracked_count"],
        "aiInsight": ai_insight,
        "reading": reading,
        "hoursPerCategory": {cat: round(mins / 60, 2) for cat, mins in stats["category_minutes"].items()},
        "topActivities": [l["response"] for l in logs if l.get("response")][:5],
        "saved_at": datetime.now(timezone.utc)
    }
    
    await db.daily_snapshots.update_one(
        {"date": today_str},
        {"$set": snapshot},
        upsert=True
    )

    # 5. Build and Send Email
    # Use services/email_template.py for consistent styling
    # stats dictionary needs to match what generate_html_email expects (categoryBreakdown, etc.)
    enriched_stats = {
        "categoryBreakdown": stats["category_minutes"],
        "totalPings": stats["total_pings"],
        "trackedCount": stats["total_pings"] - stats["untracked_count"],
        "untrackedPercent": int(stats["untracked_count"] / stats["total_pings"] * 100) if stats["total_pings"] > 0 else 0
    }

    # Convert timestamps for template
    for item in logs + notes + agenda:
        item["_id"] = str(item["_id"])
        for field in ["timestamp", "completedAt", "createdAt"]:
            if field in item and isinstance(item[field], datetime):
                dt = item[field]
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                item[field] = dt.astimezone(user_tz).isoformat()

    email_html = generate_html_email(
        logs=logs,
        agenda=agenda,
        notes=notes,
        stats=enriched_stats,
        date_str=today_str,
        ai_insight=ai_insight,
        reading=reading
    )
    
    # Add reading section to help email template if not already there?
    # services/email_template.py doesn't seem to have a reading block yet.
    # I should update services/email_template.py first.
    
    subject = f"PingMe {today_str} | Study: {format_duration(stats['study_minutes'])} | 📖 {reading['snippetsRead']} snippets | {stats['agenda_completed']}/{stats['agenda_total']} done"

    try:
        await send_email(subject, email_html)
    except Exception as e:
        print(f"DEBUG: Email failed: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

    # 6. Wipe logs (Rule: wiped weekly? DATA_MODELS says ✅ Yes — after daily snapshot saved)
    # Wait, DATA_MODELS says "logs: Wiped weekly? ✅ Yes". 
    # Usually this means after the daily snapshot is COMPLETED if we want to save space.
    # But let's check the wipe rule again. "logs: ✅ Yes — after daily snapshot saved".
    # I'll implement the wipe.
    await db.logs.delete_many(query)

    return {"sent": True}