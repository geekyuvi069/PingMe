import os
from fastapi import APIRouter, Depends, Header, HTTPException
from services.db import get_db
from services.email import send_email
from services.ai import generate_weekly_insight
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

router = APIRouter(prefix="/api/summary/weekly", tags=["weekly"])

CRON_SECRET = os.getenv("CRON_SECRET")

from services.summary import format_duration

@router.post("/")
@router.post("")
async def trigger_weekly_rollup(x_cron_secret: str = Header(None), db = Depends(get_db)):
    """Sunday weekly rollup process."""
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    # 1. Fetch last 7 daily_snapshots
    cursor = db.daily_snapshots.find().sort("date", -1).limit(7)
    snapshots = await cursor.to_list(length=7)
    
    if not snapshots:
        return {"status": "no_data"}
        
    # 2. Aggregate stats
    total_hours_per_cat = {}
    total_study_mins = 0
    total_active_mins = 0
    total_agenda_done = 0
    total_agenda_total = 0
    top_activities = []
    
    reading_stats = {
        "totalSnippets": 0,
        "totalWords": 0,
        "booksProgressed": {}
    }
    
    for s in snapshots:
        # Aggregating categories
        hpc = s.get("hoursPerCategory", {})
        for cat, hours in hpc.items():
            total_hours_per_cat[cat] = total_hours_per_cat.get(cat, 0) + hours
            
        total_study_mins += s.get("study_minutes", 0)
        total_active_mins += s.get("active_minutes", 0)
        total_agenda_done += s.get("agenda_completed", 0)
        total_agenda_total += s.get("agenda_total", 0)
        
        # Merge top activities
        top_activities.extend(s.get("topActivities", []))
        
        # Reading rollup
        rs = s.get("reading", {})
        reading_stats["totalSnippets"] += rs.get("snippetsRead", 0)
        reading_stats["totalWords"] += rs.get("wordsRead", 0)
        
        bp = rs.get("bookProgress", {})
        for title, p in bp.items():
            if title not in reading_stats["booksProgressed"]:
                reading_stats["booksProgressed"][title] = {"startPct": p["pct"], "endPct": p["pct"]}
            else:
                reading_stats["booksProgressed"][title]["endPct"] = p["pct"]
    
    # Calculate deltas for reading
    for title in reading_stats["booksProgressed"]:
        rp = reading_stats["booksProgressed"][title]
        rp["delta"] = rp["endPct"] - rp["startPct"]

    top_activities = list(set(top_activities))[:10]
    
    # 3. Generate AI Insight
    weekly_aggregated_stats = {
        "totalHours": round(total_active_mins / 60, 1),
        "studyHours": round(total_study_mins / 60, 1),
        "agendaCompletion": f"{total_agenda_done}/{total_agenda_total}",
        "readingSnippets": reading_stats["totalSnippets"]
    }
    
    ai_insight = await generate_weekly_insight(
        weekly_aggregated_stats, 
        snapshots, 
        top_activities
    )
    
    # 4. Save Weekly Snapshot
    week_start = snapshots[-1]["date"]
    week_end = snapshots[0]["date"]
    
    weekly_snapshot = {
        "weekStart": week_start,
        "weekEnd": week_end,
        "generatedAt": datetime.now(timezone.utc),
        "totalHoursPerCategory": total_hours_per_cat,
        "studyMinutes": total_study_mins,
        "agenda_completed": total_agenda_done,
        "agenda_total": total_agenda_total,
        "aiInsight": ai_insight,
        "reading": reading_stats,
        "topActivities": top_activities
    }
    
    await db.weekly_snapshots.insert_one(weekly_snapshot)
    
    # 5. Build and Send Email (simplified for now, ideally use a template)
    subject = f"PingMe Weekly Rollup | {week_start} → {week_end}"
    email_html = f"""
    <div style="background:#0a0a14;color:#e2e8f0;padding:20px;font-family:sans-serif;">
        <h1 style="color:#4ade80;">Weekly Snapshot</h1>
        <p>{week_start} to {week_end}</p>
        <div style="background:#0d1f12;padding:15px;border-left:4px solid #4ade80;margin:20px 0;">
            <h3>AI Weekly Insight</h3>
            <p style="font-style:italic;">{ai_insight}</p>
        </div>
        <h3>Stats</h3>
        <ul>
            <li>Total Active: {format_duration(total_active_mins)}</li>
            <li>Status/Deep Work: {format_duration(total_study_mins)}</li>
            <li>Agenda Completion: {total_agenda_done}/{total_agenda_total} ({int(total_agenda_done/total_agenda_total*100) if total_agenda_total > 0 else 0}%)</li>
        </ul>
        <h3>Reading Rollup</h3>
        <p>You read <b>{reading_stats['totalSnippets']} snippets</b> (~{reading_stats['totalWords']} words) this week.</p>
    </div>
    """
    
    await send_email(subject, email_html)
    
    # 6. Delete daily snapshots (Wipe rule)
    snapshot_ids = [s["_id"] for s in snapshots]
    await db.daily_snapshots.delete_many({"_id": {"$in": snapshot_ids}})
    
    return {"status": "success", "week": f"{week_start} to {week_end}"}
