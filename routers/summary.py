import os
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from services.db import get_db
from services.telegram import send_message as send_telegram
from services.email import send_email
from services.ai import generate_ai_summary
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

router = APIRouter(prefix="/api/summary", tags=["summary"])

CRON_SECRET = os.getenv("CRON_SECRET")


def extract_top_activities(logs: list, top_n: int = 5) -> list:
    """Pull the most frequent non-empty response texts from logs."""
    from collections import Counter
    responses = [
        l["response"].strip().lower()
        for l in logs
        if l.get("response") and not l.get("skipped") and not l.get("untracked")
    ]
    most_common = Counter(responses).most_common(top_n)
    return [text for text, _ in most_common]


def compute_hours_per_category(logs: list, interval_minutes: int = 15) -> dict:
    """Convert ping counts per category into approximate hours."""
    category_counts: Dict[str, int] = {}
    for log in logs:
        if not log.get("skipped") and not log.get("untracked"):
            cat = log.get("category", "untracked")
            category_counts[cat] = category_counts.get(cat, 0) + 1

    hours = {}
    for cat, count in category_counts.items():
        hours[cat] = round((count * interval_minutes) / 60, 2)
    return hours


@router.get("/")
async def get_summary(db=Depends(get_db)):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Fetch logs, notes, agenda
    logs_cursor = db.logs.find({"timestamp": {"$gte": today_start}}).sort("timestamp", 1)
    logs = await logs_cursor.to_list(length=500)

    notes_cursor = db.notes.find({"timestamp": {"$gte": today_start}}).sort("timestamp", 1)
    notes = await notes_cursor.to_list(length=100)

    agenda_cursor = db.agenda.find({"date": today})
    agenda = await agenda_cursor.to_list(length=100)

    # Stats
    total_pings = len(logs)
    tracked_count = sum(
        1 for l in logs if not l.get("skipped") and not l.get("untracked")
    )
    untracked_count = sum(1 for l in logs if l.get("untracked"))
    untracked_percent = (
        int((untracked_count / total_pings * 100)) if total_pings > 0 else 0
    )

    category_breakdown: Dict[str, int] = {}
    for log in logs:
        if not log.get("skipped") and not log.get("untracked"):
            cat = log.get("category", "untracked")
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

    # Serialize ObjectIds and datetimes
    for item in logs + notes + agenda:
        item["_id"] = str(item["_id"])
        for field in ("timestamp", "completedAt", "createdAt"):
            if field in item and isinstance(item[field], datetime):
                item[field] = item[field].isoformat()

    return {
        "date": today,
        "logs": logs,
        "notes": notes,
        "agenda": agenda,
        "stats": {
            "totalPings": total_pings,
            "trackedCount": tracked_count,
            "untrackedCount": untracked_count,
            "untrackedPercent": untracked_percent,
            "categoryBreakdown": category_breakdown,
        },
    }


async def _save_daily_snapshot(db, summary: dict, email_html: str):
    """
    Persist a compact daily snapshot so we can roll it up into a weekly
    snapshot later — then we can safely discard the raw logs.
    """
    date_str = summary["date"]
    stats = summary["stats"]

    # Check if a snapshot for today already exists (idempotent re-runs)
    existing = await db.daily_snapshots.find_one({"date": date_str})
    if existing:
        print(f"DEBUG: daily_snapshot for {date_str} already exists — skipping.", flush=True)
        return

    snapshot = {
        "date": date_str,
        "createdAt": datetime.now(timezone.utc),
        "stats": {
            "totalPings": stats["totalPings"],
            "trackedCount": stats["trackedCount"],
            "untrackedCount": stats["untrackedCount"],
            "untrackedPercent": stats["untrackedPercent"],
            "categoryBreakdown": stats["categoryBreakdown"],
        },
        "hoursPerCategory": compute_hours_per_category(summary["logs"]),
        "topActivities": extract_top_activities(summary["logs"]),
        "agendaCompleted": sum(1 for i in summary["agenda"] if i.get("completed")),
        "agendaTotal": len(summary["agenda"]),
        "notesCount": len(summary["notes"]),
        # Store AI-generated email text so weekly rollup can reference it
        "summaryText": email_html,
    }

    await db.daily_snapshots.insert_one(snapshot)
    print(f"DEBUG: Saved daily_snapshot for {date_str}", flush=True)


async def _delete_old_logs(db):
    """
    Delete all logs strictly before today (UTC midnight).
    Today's logs are kept so the dashboard still works until end of day.
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.logs.delete_many({"timestamp": {"$lt": today_start}})
    print(
        f"DEBUG: Deleted {result.deleted_count} old log entries (before {today_start.date()})",
        flush=True,
    )


@router.post("/send")
@router.post("/send/")
async def send_summary(x_cron_secret: str = Header(None), db=Depends(get_db)):
    print(f"DEBUG: Starting send_summary. Received secret: {x_cron_secret}", flush=True)

    if x_cron_secret != CRON_SECRET:
        print(f"DEBUG: Forbidden. Expected: {CRON_SECRET}, Got: {x_cron_secret}", flush=True)
        raise HTTPException(status_code=403, detail="Forbidden")

    print("DEBUG: Secret verified. Fetching summary data...", flush=True)
    summary = await get_summary(db)

    date_str = summary["date"]
    stats = summary["stats"]

    # ── Telegram message ──────────────────────────────────────────────────────
    time_log = ""
    for log in summary["logs"]:
        ts = log["timestamp"]
        time = datetime.fromisoformat(ts).strftime("%H:%M") if isinstance(ts, str) else ts.strftime("%H:%M")
        content = log.get("response") or ("[skipped]" if log.get("skipped") else "[untracked]")
        cat = f" [{log.get('category')}]" if log.get("category") else ""
        time_log += f"  {time} — {content}{cat}\n"

    agenda_text = "".join(
        f"  {'✅' if i['completed'] else '⏳'} {i['content']}\n"
        for i in summary["agenda"]
    )
    notes_text = "\n".join(f"  • {n['content']}" for n in summary["notes"])
    priorities = "\n".join(
        f"  • {i['content']}" for i in summary["agenda"] if not i["completed"]
    )

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

    # ── AI email ──────────────────────────────────────────────────────────────
    print("DEBUG: Calling Gemini AI for summary...", flush=True)
    email_html = ""
    try:
        email_html = await generate_ai_summary(
            summary["logs"], summary["agenda"], summary["notes"],summary["stats"]
        )
        if email_html:
            print("DEBUG: Gemini AI generated summary successfully", flush=True)
        else:
            print("DEBUG: Gemini AI returned empty summary (fallback will be used)", flush=True)
    except Exception as e:
        print(f"DEBUG: Gemini AI Summary failed: {e}", flush=True)
        email_html = f"<h1>Daily Summary - {date_str}</h1><pre>{time_log}</pre>"

    if not email_html:
        email_html = f"<h1>Daily Summary - {date_str}</h1><pre>{time_log}</pre>"

    print("DEBUG: Sending email via Resend...", flush=True)
    try:
        await send_email(f"PingMe Summary — {date_str} ✨", email_html)
        print("DEBUG: Email sent successfully", flush=True)
    except Exception as ee:
        print(f"DEBUG: Email sending failed: {ee}", flush=True)
        raise HTTPException(status_code=500, detail=str(ee))

    # ── Save snapshot → delete old logs ───────────────────────────────────────
    print("DEBUG: Saving daily snapshot...", flush=True)
    await _save_daily_snapshot(db, summary, email_html)

    print("DEBUG: Deleting old logs...", flush=True)
    await _delete_old_logs(db)

    return {"sent": True}
