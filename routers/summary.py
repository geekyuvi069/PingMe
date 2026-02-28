import os
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from services.db import get_db
from services.telegram import send_message as send_telegram
from services.email import send_email
from services.email_template import generate_html_email
from services.ai import generate_ai_summary
from datetime import datetime, timezone
from typing import Dict, Any

router = APIRouter(prefix="/api/summary", tags=["summary"])

CRON_SECRET = os.getenv("CRON_SECRET")

@router.get("/")
async def get_summary(db = Depends(get_db)):
    from datetime import timedelta

    # Always show YESTERDAY's data
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_start = (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)

    logs_cursor = db.logs.find({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_end}}).sort("timestamp", 1)
    logs = await logs_cursor.to_list(length=200)

    notes_cursor = db.notes.find({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_end}}).sort("timestamp", 1)
    notes = await notes_cursor.to_list(length=100)

    agenda_cursor = db.agenda.find({"date": yesterday})
    agenda = await agenda_cursor.to_list(length=100)
    
    total_pings = len(logs)
    tracked_count = sum(1 for l in logs if not l.get("skipped") and not l.get("untracked"))
    untracked_count = sum(1 for l in logs if l.get("untracked"))
    untracked_percent = int((untracked_count / total_pings * 100)) if total_pings > 0 else 0
    
    category_breakdown = {}
    for log in logs:
        if not log.get("skipped") and not log.get("untracked"):
            cat = log.get("category", "untracked")
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
    
    for item in logs + notes + agenda:
        item["_id"] = str(item["_id"])
        if "timestamp" in item:
            if isinstance(item["timestamp"], datetime):
                item["timestamp"] = item["timestamp"].isoformat()
        if "completedAt" in item and item["completedAt"]:
            if isinstance(item["completedAt"], datetime):
                item["completedAt"] = item["completedAt"].isoformat()
        if "createdAt" in item:
            if isinstance(item["createdAt"], datetime):
                item["createdAt"] = item["createdAt"].isoformat()
            
    return {
        "date": yesterday,
        "logs": logs,
        "notes": notes,
        "agenda": agenda,
        "stats": {
            "totalPings": total_pings,
            "trackedCount": tracked_count,
            "untrackedCount": untracked_count,
            "untrackedPercent": untracked_percent,
            "categoryBreakdown": category_breakdown
        }
    }

@router.post("/send")
@router.post("/send/")
async def send_summary(x_cron_secret: str = Header(None), db = Depends(get_db)):
    print(f"DEBUG: Starting send_summary. Received secret: {x_cron_secret}", flush=True)
    
    if x_cron_secret != CRON_SECRET:
        print(f"DEBUG: Forbidden. Expected: {CRON_SECRET}, Got: {x_cron_secret}", flush=True)
        raise HTTPException(status_code=403, detail="Forbidden")
        
    print("DEBUG: Secret verified. Fetching summary data...", flush=True)
    summary = await get_summary(db)
    
    # --- Format Telegram Message (plain text, unchanged) ---
    date_str = summary["date"]
    stats = summary["stats"]
    
    time_log = ""
    for log in summary["logs"]:
        ts = log["timestamp"]
        if isinstance(ts, str):
            time = datetime.fromisoformat(ts).strftime("%H:%M")
        else:
            time = ts.strftime("%H:%M")
        content = log.get("response", "[skipped]" if log.get("skipped") else "[untracked]")
        cat = f" [{log.get('category')}]" if log.get('category') else ""
        time_log += f"  {time} — {content}{cat}\n"
        
    agenda_text = ""
    for item in summary["agenda"]:
        status = "✅" if item["completed"] else "⏳"
        agenda_text += f"  {status} {item['content']}\n"
        
    notes_text = "\n".join([f"  • {n['content']}" for n in summary["notes"]])
    priorities = "\n".join([f"  • {i['content']}" for i in summary["agenda"] if not i["completed"]])
    
    tg_msg = (
        f"<b>📊 Your Day — {date_str}</b>\n\n"
        f"<b>⏱️ Time Log</b>\n{time_log}\n"
        f"<b>📈 Stats</b>\n"
        f"  Tracked: {stats['trackedCount']}  |  Untracked: {stats['untrackedPercent']}%\n\n"
        f"<b>📋 Agenda</b>\n{agenda_text}\n"
        f"<b>🗒️ Notes</b>\n{notes_text}\n\n"
        f"<b>🔜 Tomorrow's Priorities</b>\n{priorities}"
    )
    
    print("DEBUG: Sending Telegram message...", flush=True)
    try:
        await send_telegram(tg_msg)
    except Exception as te:
        print(f"DEBUG: Telegram send failed: {te}", flush=True)
    
    # --- Call Gemini for AI insight ---
    print("DEBUG: Calling Gemini for AI insight...", flush=True)
    ai_insight = ""
    try:
        ai_insight = await generate_ai_summary(
            logs=summary["logs"],
            agenda=summary["agenda"],
            notes=summary["notes"],
            stats=summary["stats"]
        )
        print(f"DEBUG: AI insight generated: {ai_insight[:80]}...", flush=True)
    except Exception as e:
        print(f"DEBUG: AI insight failed (email will still send): {e}", flush=True)

    # --- Generate rich HTML email with charts ---
    print("DEBUG: Generating HTML email with charts...", flush=True)
    
    # Fetch interval setting for accurate time calculations
    settings = await db.settings.find_one({"userId": "default"})
    interval_minutes = settings.get("intervalMinutes", 15) if settings else 15
    
    try:
        email_html = generate_html_email(
            logs=summary["logs"],
            agenda=summary["agenda"],
            notes=summary["notes"],
            stats=summary["stats"],
            date_str=date_str,
            interval_minutes=interval_minutes,
            ai_insight=ai_insight
        )
        print("DEBUG: HTML email generated successfully", flush=True)
    except Exception as e:
        print(f"DEBUG: HTML email generation failed: {e}", flush=True)
        # Minimal fallback
        email_html = f"<h1>Daily Summary — {date_str}</h1><pre>{time_log}</pre>"
    
    print("DEBUG: Sending email via Resend...", flush=True)
    try:
        await send_email(f"📊 PingMe — {date_str}", email_html)
        print("DEBUG: Email sent successfully", flush=True)
    except Exception as ee:
        print(f"DEBUG: Email sending failed: {ee}", flush=True)
        raise HTTPException(status_code=500, detail=str(ee))
    
    return {"sent": True}