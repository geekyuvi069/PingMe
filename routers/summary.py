import os
import pytz
from fastapi import APIRouter, Depends, Header, HTTPException
from services.db import get_db
from services.email import send_email
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/summary", tags=["summary"])

CRON_SECRET = os.getenv("CRON_SECRET")
PING_INTERVAL_MINUTES = 15


async def get_today_range(db):
    """
    Returns (start_utc, end_utc, date_str) for the user's local day.
    """
    settings = await db.settings.find_one({"userId": "default"})
    tz_str = settings.get("timezone", "Asia/Kolkata") if settings else "Asia/Kolkata"
    user_tz = pytz.timezone(tz_str)
    
    now_local = datetime.now(user_tz)
    # If called right after midnight (e.g. 00:05), it's likely summarizing the day that just ended.
    # But usually, it triggers at a set time. Let's stick to 'now' logic for daily view.
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
        "agenda_incomplete": [i for i in agenda if not i.get("completed")],
        "category_minutes": category_minutes,
    }


def build_html_email(date_str, logs, agenda, notes, stats, first_time=None, last_time=None):
    active_window = f"{first_time} → {last_time}" if first_time and last_time else "–"

    study_str = format_duration(stats["study_minutes"])
    active_str = format_duration(stats["active_minutes"])
    total_minutes = stats["active_minutes"] + stats["untracked_minutes"] or 1

    def pct(mins):
        return round(mins / total_minutes * 100)

    def bar_row(emoji, label, mins, color_start, color_end):
        if not mins:
            return ""
        return f"""
        <div style="margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="font-size:14px;color:#e2e8f0;">{emoji} {label}</span>
            <span style="font-size:14px;font-weight:700;color:{color_end};">{format_duration(mins)}</span>
          </div>
          <div style="background:#1e293b;border-radius:999px;height:6px;overflow:hidden;">
            <div style="background:linear-gradient(90deg,{color_start},{color_end});height:100%;width:{pct(mins)}%;border-radius:999px;"></div>
          </div>
        </div>"""

    time_bars = bar_row("🧠", "Study / Deep Work", stats["study_minutes"], "#22c55e", "#4ade80")
    time_bars += bar_row("☕", "Break", stats["break_minutes"], "#3b82f6", "#60a5fa")
    time_bars += bar_row("📬", "Admin", stats["admin_minutes"], "#9333ea", "#c084fc")
    time_bars += bar_row("🤝", "Meetings", stats["meetings_minutes"], "#d97706", "#fbbf24")
    time_bars += bar_row("😵", "Distracted", stats["distracted_minutes"], "#ef4444", "#f87171")

    untracked_row = ""
    if stats["untracked_minutes"]:
        untracked_row = f"""
        <div style="padding-top:16px;border-top:1px solid #1e293b;display:flex;justify-content:space-between;">
          <span style="font-size:13px;color:#475569;">❓ Untracked / Skipped</span>
          <span style="font-size:13px;color:#475569;">{format_duration(stats["untracked_minutes"])}</span>
        </div>"""

    agenda_pct = round(stats["agenda_completed"] / stats["agenda_total"] * 100) if stats["agenda_total"] else 0
    agenda_items_html = ""
    for item in agenda:
        done = item.get("completed")
        icon = "✅" if done else "⏳"
        text_style = "color:#64748b;text-decoration:line-through;" if done else "color:#e2e8f0;"
        bg = "background:#0a0f1e;border:1px solid #1e293b;" if done else "background:#120a0a;border:1px solid #2d1515;"
        carried = "<span style='margin-left:auto;font-size:10px;color:#475569;background:#1e293b;padding:2px 7px;border-radius:999px;white-space:nowrap;'>from yesterday</span>" if item.get("carriedFrom") else ""
        agenda_items_html += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;{bg}border-radius:8px;margin-bottom:8px;">
          <span>{icon}</span>
          <span style="font-size:14px;{text_style}flex:1;">{item['content']}</span>
          {carried}
        </div>"""

    if not agenda_items_html:
        agenda_items_html = "<div style='color:#475569;font-style:italic;font-size:14px;'>No agenda items today</div>"

    priority_html = ""
    for item in stats["agenda_incomplete"]:
        priority_html += f"""
        <div style="display:flex;align-items:center;gap:10px;color:#e2e8f0;font-size:14px;padding:4px 0;">
          <span style="color:#f59e0b;font-size:12px;">▶</span> {item['content']}
        </div>"""
    if not priority_html:
        priority_html = "<div style='color:#4ade80;font-size:14px;'>All tasks completed 🎉</div>"

    notes_section = ""
    if notes:
        notes_html = ""
        for note in notes:
            ts = note["timestamp"]
            t = datetime.fromisoformat(ts).strftime("%H:%M") if isinstance(ts, str) else ts.strftime("%H:%M")
            notes_html += f"""
            <div style="padding:12px 14px;background:#0a0f1e;border-left:3px solid #3b82f6;border-radius:0 8px 8px 0;margin-bottom:8px;">
              <div style="font-size:11px;color:#475569;margin-bottom:4px;">{t}</div>
              <div style="font-size:14px;color:#e2e8f0;">{note['content']}</div>
            </div>"""
        notes_section = f"""
        <div style="background:#0d1117;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:20px;">
          <h2 style="margin:0 0 16px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">🗒 Notes Captured</h2>
          {notes_html}
        </div>"""

    cat_styles = {
        "deep_work":  ("#4ade80", "#0f2618"),
        "break":      ("#60a5fa", "#0c1a2e"),
        "admin":      ("#c084fc", "#1a0f2e"),
        "meetings":   ("#fbbf24", "#1c1200"),
        "distracted": ("#f87171", "#1c0a0a"),
    }
    log_rows_html = ""
    for log in logs:
        ts = log["timestamp"]
        t = datetime.fromisoformat(ts).strftime("%H:%M") if isinstance(ts, str) else ts.strftime("%H:%M")
        if log.get("skipped") or log.get("untracked"):
            content = "<span style='color:#475569;font-style:italic;'>skipped / untracked</span>"
            badge = "<span style='font-size:10px;color:#334155;background:#0f172a;padding:2px 8px;border-radius:999px;'>–</span>"
        else:
            content = f"<span style='color:#e2e8f0;'>{log.get('response', '')}</span>"
            cat = log.get("category", "")
            color, bg = cat_styles.get(cat, ("#94a3b8", "#1e293b"))
            badge = f"<span style='font-size:10px;font-weight:700;color:{color};background:{bg};padding:2px 8px;border-radius:999px;text-transform:uppercase;white-space:nowrap;'>{cat.replace('_', ' ')}</span>"
        log_rows_html += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #0f172a;">
          <span style="font-size:12px;color:#475569;min-width:38px;font-family:monospace;">{t}</span>
          <span style="font-size:13px;flex:1;">{content}</span>
          {badge}
        </div>"""

    if not log_rows_html:
        log_rows_html = "<div style='color:#475569;font-style:italic;font-size:14px;'>No logs today</div>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e2e8f0;">
<div style="max-width:620px;margin:0 auto;padding:32px 16px;">

  <div style="text-align:center;padding:40px 32px;background:linear-gradient(135deg,#0d1b2a 0%,#1a1040 50%,#0d1b2a 100%);border-radius:16px;margin-bottom:24px;border:1px solid #1e293b;">
    <div style="font-size:36px;margin-bottom:8px;">📊</div>
    <h1 style="margin:0 0 6px;font-size:26px;font-weight:700;color:#f8fafc;letter-spacing:-0.5px;">Daily Summary</h1>
    <p style="margin:0;color:#64748b;font-size:14px;">{date_str} &nbsp;·&nbsp; Active: {active_window}</p>
  </div>

  <table style="width:100%;border-collapse:separate;border-spacing:12px;margin:-12px 0 12px;">
    <tr>
      <td style="background:#0f2618;border:1px solid #166534;border-radius:12px;padding:20px 16px;text-align:center;width:33%;">
        <div style="font-size:22px;margin-bottom:4px;">🧠</div>
        <div style="font-size:26px;font-weight:800;color:#4ade80;line-height:1;">{study_str}</div>
        <div style="font-size:11px;color:#16a34a;margin-top:6px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Study Time</div>
      </td>
      <td style="background:#0c1a2e;border:1px solid #1e40af;border-radius:12px;padding:20px 16px;text-align:center;width:33%;">
        <div style="font-size:22px;margin-bottom:4px;">⚡</div>
        <div style="font-size:26px;font-weight:800;color:#60a5fa;line-height:1;">{active_str}</div>
        <div style="font-size:11px;color:#3b82f6;margin-top:6px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Total Active</div>
      </td>
      <td style="background:#1a0f2e;border:1px solid #6b21a8;border-radius:12px;padding:20px 16px;text-align:center;width:33%;">
        <div style="font-size:22px;margin-bottom:4px;">✅</div>
        <div style="font-size:26px;font-weight:800;color:#c084fc;line-height:1;">{stats['agenda_completed']}/{stats['agenda_total']}</div>
        <div style="font-size:11px;color:#9333ea;margin-top:6px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Tasks Done</div>
      </td>
    </tr>
  </table>

  <div style="background:#0d1117;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:20px;">
    <h2 style="margin:0 0 20px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">⏱ Time Breakdown</h2>
    {time_bars}
    {untracked_row}
  </div>

  <div style="background:#0d1117;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:20px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
      <h2 style="margin:0;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">📋 Agenda</h2>
      <span style="font-size:12px;color:#64748b;background:#1e293b;padding:3px 10px;border-radius:999px;">{stats['agenda_completed']} of {stats['agenda_total']} done</span>
    </div>
    <div style="background:#1e293b;border-radius:999px;height:4px;margin-bottom:20px;overflow:hidden;">
      <div style="background:linear-gradient(90deg,#9333ea,#c084fc);height:100%;width:{agenda_pct}%;border-radius:999px;"></div>
    </div>
    <div>{agenda_items_html}</div>
  </div>

  <div style="background:#0d1117;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:20px;">
    <h2 style="margin:0 0 16px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">🔜 Tomorrow's Priorities</h2>
    {priority_html}
  </div>

  {notes_section}

  <div style="background:#0d1117;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:24px;">
    <h2 style="margin:0 0 16px;font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">📜 Full Time Log</h2>
    {log_rows_html}
  </div>

  <div style="text-align:center;padding:20px;">
    <p style="margin:0;font-size:12px;color:#334155;">PingMe &nbsp;·&nbsp; your honest daily log</p>
  </div>

</div>
</body>
</html>"""


@router.get("/")
async def get_summary(db=Depends(get_db)):
    utc_start, utc_end, today_str, user_tz = await get_today_range(db)

    # Use range query to be precise
    query = {"timestamp": {"$gte": utc_start, "$lt": utc_end}}
    logs = await db.logs.find(query).sort("timestamp", 1).to_list(200)
    notes = await db.notes.find(query).sort("timestamp", 1).to_list(100)
    agenda = await db.agenda.find({"date": today_str}).to_list(100)

    stats = compute_stats(logs, agenda)

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

    # Use range query to be precise
    query = {"timestamp": {"$gte": utc_start, "$lt": utc_end}}
    logs = await db.logs.find(query).sort("timestamp", 1).to_list(200)
    notes = await db.notes.find(query).sort("timestamp", 1).to_list(100)
    agenda = await db.agenda.find({"date": today_str}).to_list(100)

    stats = compute_stats(logs, agenda)

    tracked = [l for l in logs if not l.get("skipped") and not l.get("untracked")]
    
    def ts_fmt(dt):
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(user_tz).strftime("%H:%M")

    first_time = ts_fmt(tracked[0]["timestamp"]) if tracked else None
    last_time = ts_fmt(tracked[-1]["timestamp"]) if tracked else None

    # Convert everything for the template & snapshot
    for item in logs + notes + agenda:
        item["_id"] = str(item["_id"])
        for field in ["timestamp", "completedAt", "createdAt"]:
            if field in item and isinstance(item[field], datetime):
                dt = item[field]
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                item[field] = dt.astimezone(user_tz).isoformat()

    # --- Minimal Snapshot for Weekly Review ---
    snapshot = {
        "date": today_str,
        "study_minutes": stats["study_minutes"],
        "distracted_minutes": stats["distracted_minutes"],
        "active_minutes": stats["active_minutes"],
        "agenda_completed": stats["agenda_completed"],
        "agenda_total": stats["agenda_total"],
        "saved_at": datetime.now(timezone.utc),
        # Keep hoursPerCategory for weekly aggregation compatibility
        "hoursPerCategory": {cat: round(mins / 60, 2) for cat, mins in stats["category_minutes"].items()},
        "topActivities": [l["response"] for l in tracked if l.get("response")][:5]
    }
    
    await db.daily_snapshots.update_one(
        {"date": today_str},
        {"$set": snapshot},
        upsert=True
    )


    # Email
    email_html = build_html_email(today_str, logs, agenda, notes, stats, first_time, last_time)
    subject = f"PingMe {today_str} | Study: {format_duration(stats['study_minutes'])} | {stats['agenda_completed']}/{stats['agenda_total']} done"

    try:
        await send_email(subject, email_html)
    except Exception as e:
        print(f"DEBUG: Email failed: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {"sent": True}