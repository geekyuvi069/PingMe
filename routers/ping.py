import os
from fastapi import APIRouter, Depends, Header, HTTPException, Body
from services.db import get_db
from services.categorize import categorize
from services.telegram import send_message as send_telegram
from datetime import datetime, timezone, timedelta
import pytz
from typing import Dict, Any

router = APIRouter(prefix="/api/ping", tags=["ping"])

CRON_SECRET = os.getenv("CRON_SECRET")

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
    # Simplified morning kickoff check for now: if lastMorningMessage != today
    today_str = now.strftime("%Y-%m-%d")
    if settings.get("lastMorningMessage") != today_str:
        # It's time for morning kickoff
        from routers.agenda import carryforward_agenda
        await carryforward_agenda(db)
        
        # Get today's agenda
        cursor = db.agenda.find({"date": today_str})
        agenda_items = await cursor.to_list(length=100)
        agenda_text = "\n".join([f"- {'✅' if i['completed'] else '☐'} {i['content']}" for i in agenda_items])
        
        msg = f"<b>Good morning! ☀️</b>\n\n<b>📋 Today's Agenda</b>\n{agenda_text}\n\nHave a great day!"
        await send_telegram(msg)
        await db.settings.update_one({"userId": "default"}, {"$set": {"lastMorningMessage": today_str}})
    else:
        await send_telegram("Hey! What are you doing? 👀")
        
    return {"fired": True}

@router.get("/status/")
async def get_status(db = Depends(get_db)):
    settings = await db.settings.find_one({"userId": "default"})
    if not settings:
        return {"pending": False, "askedAt": None}
    return {
        "pending": settings.get("pendingPing", False),
        "askedAt": settings.get("pendingPingAt")
    }

@router.post("/respond/")
async def respond_ping(data: Dict[str, Any] = Body(...), db = Depends(get_db)):
    response_text = data.get("response")
    skipped = data.get("skipped", False)
    untracked = data.get("untracked", False)
    
    category = "untracked"
    if not skipped and not untracked and response_text:
        category = categorize(response_text)
        
    log_entry = {
        "timestamp": datetime.now(timezone.utc),
        "response": response_text,
        "source": data.get("source", "unknown"),
        "skipped": skipped,
        "untracked": untracked,
        "category": category,
        "categorySource": "keyword" if response_text else "system"
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
