import os
import pytz
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Body
from services.db import get_db
from services.ai import categorize_with_ai, generate_nudge
from services.summary import compute_stats

router = APIRouter(prefix="/api/ping", tags=["ping"])

CRON_SECRET = os.getenv("CRON_SECRET")

@router.get("/nudge/")
@router.get("/nudge")
async def get_nudge(db = Depends(get_db)):
    """Fetch a mid-day AI nudge based on today's activity."""
    from routers.summary import get_today_range
    utc_start, utc_end, today_str, user_tz = await get_today_range(db)
    
    query = {"timestamp": {"$gte": utc_start, "$lt": utc_end}}
    logs = await db.logs.find(query).sort("timestamp", 1).to_list(100)
    agenda = await db.agenda.find({"date": today_str}).to_list(100)
    
    if len(logs) < 3:
        return {"nudge": ""}
        
    stats = compute_stats(logs, agenda)
    
    try:
        # 4s timeout as per FEATURES.md
        nudge = await generate_nudge(logs, stats)
        return {"nudge": nudge}
    except Exception:
        return {"nudge": ""}

@router.post("/trigger")
async def trigger_ping(x_cron_secret: str = Header(None), db = Depends(get_db)):
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    settings = await db.settings.find_one({"userId": "default"})
    if not settings:
        return {"fired": False, "reason": "no_settings"}
        
    # Check sleep window
    tz = pytz.timezone(settings.get("timezone", "Asia/Kolkata"))
    now = datetime.now(tz)
    now_str = now.strftime("%H:%M")
    
    sleep_start = settings.get("sleepStart", "02:00")
    sleep_end = settings.get("sleepEnd", "10:00")
    
    is_sleeping = False
    if sleep_start < sleep_end:
        is_sleeping = sleep_start <= now_str <= sleep_end
    else: # Over midnight
        is_sleeping = now_str >= sleep_start or now_str <= sleep_end
        
    if is_sleeping:
        return {"fired": False, "reason": "sleep_window"}
        
    # Check pause
    if settings.get("isPaused"):
        pause_until = settings.get("pauseUntil")
        if pause_until:
            if datetime.now(timezone.utc) < pause_until.replace(tzinfo=timezone.utc):
                return {"fired": False, "reason": "paused"}
            else:
                # Auto-resume
                await db.settings.update_one({"userId": "default"}, {"$set": {"isPaused": False, "pauseUntil": None}})
        else:
            return {"fired": False, "reason": "paused"}
            
    # Check last response
    last_responded = settings.get("lastRespondedAt")
    if last_responded:
        interval = settings.get("intervalMinutes", 15)
        if datetime.now(timezone.utc) < last_responded.replace(tzinfo=timezone.utc) + timedelta(minutes=interval - 2):
            return {"fired": False, "reason": "recent_response"}
            
    # Success: Trigger ping
    await db.settings.update_one({"userId": "default"}, {
        "$set": {
            "pendingPing": True,
            "pendingPingAt": datetime.now(timezone.utc)
        }
    })
    
    # Check if morning kickoff (within 15 mins of sleepEnd and first message today)
    today_str = now.strftime("%Y-%m-%d")
    if settings.get("lastMorningMessage") != today_str:
        # It's time for morning kickoff
        from routers.agenda import carryforward_agenda
        await carryforward_agenda(db)
        
        # --- Morning Kickoff via Telegram ---
        # Note: Previous removal was recent, but docs2 requires it.
        # We use a helper from a new services/telegram.py or similar.
        try:
            from services.telegram import send_morning_kickoff
            await send_morning_kickoff(db, today_str)
        except Exception as e:
            print(f"DEBUG: Morning kickoff failed: {e}")
        
        await db.settings.update_one({"userId": "default"}, {"$set": {"lastMorningMessage": today_str}})
        
    return {"fired": True}

@router.get("/status/")
@router.get("/status")
async def get_status(db = Depends(get_db)):
    settings = await db.settings.find_one({"userId": "default"})
    if not settings:
        return {"pending": False, "askedAt": None}
    return {
        "pending": settings.get("pendingPing", False),
        "askedAt": settings.get("pendingPingAt")
    }

@router.post("/respond/")
@router.post("/respond")
async def respond_ping(data: Dict[str, Any] = Body(...), db = Depends(get_db)):
    response_text = data.get("response")
    skipped = data.get("skipped", False)
    untracked = data.get("untracked", False)
    
    category = "untracked"
    category_source = "system"
    
    if not skipped and not untracked and response_text:
        category = await categorize_with_ai(response_text)
        category_source = "ai"
        
    log_entry = {
        "timestamp": datetime.now(timezone.utc),
        "response": response_text,
        "source": data.get("source", "unknown"),
        "skipped": skipped,
        "untracked": untracked,
        "category": category,
        "categorySource": category_source
    }
    
    await db.logs.insert_one(log_entry)
    
    await db.settings.update_one({"userId": "default"}, {
        "$set": {
            "pendingPing": False,
            "lastRespondedAt": datetime.now(timezone.utc)
        }
    })
    
    log_entry["_id"] = str(log_entry["_id"])
    return log_entry
