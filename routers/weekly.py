import os
from fastapi import APIRouter, Depends, Header, HTTPException
from services.db import get_db
from services.telegram import send_message as send_telegram
from services.ai import generate_ai_summary
from datetime import datetime, timezone, timedelta
from collections import Counter
from typing import Dict, Any

router = APIRouter(prefix="/api/summary/weekly", tags=["weekly"])

CRON_SECRET = os.getenv("CRON_SECRET")


def _most_productive_day(daily_snapshots: list) -> str:
    """Return the date string with the highest tracked deep_work pings."""
    best_date = None
    best_count = -1
    for snap in daily_snapshots:
        breakdown = snap.get("stats", {}).get("categoryBreakdown", {})
        deep = breakdown.get("deep_work", 0)
        if deep > best_count:
            best_count = deep
            best_date = snap["date"]
    if not best_date:
        return "N/A"
    # Return as weekday name e.g. "Monday"
    try:
        return datetime.strptime(best_date, "%Y-%m-%d").strftime("%A")
    except Exception:
        return best_date


def _least_productive_day(daily_snapshots: list) -> str:
    """Return the date string with the highest untracked percent."""
    worst_date = None
    worst_pct = -1
    for snap in daily_snapshots:
        pct = snap.get("stats", {}).get("untrackedPercent", 0)
        if pct > worst_pct:
            worst_pct = pct
            worst_date = snap["date"]
    if not worst_date:
        return "N/A"
    try:
        return datetime.strptime(worst_date, "%Y-%m-%d").strftime("%A")
    except Exception:
        return worst_date


def _aggregate_category_hours(daily_snapshots: list) -> Dict[str, float]:
    """Sum up hoursPerCategory across all daily snapshots."""
    totals: Dict[str, float] = {}
    for snap in daily_snapshots:
        for cat, hrs in snap.get("hoursPerCategory", {}).items():
            totals[cat] = round(totals.get(cat, 0) + hrs, 2)
    return totals


def _top_activities_across_week(daily_snapshots: list, top_n: int = 5) -> list:
    """Flatten all topActivities lists and return the most common ones."""
    all_activities = []
    for snap in daily_snapshots:
        all_activities.extend(snap.get("topActivities", []))
    most_common = Counter(all_activities).most_common(top_n)
    return [act for act, _ in most_common]


def _build_weekly_telegram_msg(week_start: str, week_end: str, stats: dict) -> str:
    category_lines = "\n".join(
        f"  {cat}: {hrs}h"
        for cat, hrs in sorted(
            stats["totalHoursPerCategory"].items(), key=lambda x: x[1], reverse=True
        )
    )
    top_acts = "\n".join(f"  • {a}" for a in stats["topActivities"])
    daily_lines = "\n".join(
        f"  {d['date']}  deep_work: {d['deepWorkHours']}h  untracked: {d['untrackedPercent']}%"
        for d in stats["dailyBreakdown"]
    )

    msg = (
        f"<b>📅 Weekly Review — {week_start} → {week_end}</b>\n\n"
        f"<b>⏱️ Total Tracked Hours</b>\n{category_lines}\n\n"
        f"<b>📈 Weekly Stats</b>\n"
        f"  Avg untracked: {stats['avgUntrackedPercent']}%\n"
        f"  Most productive day: {stats['mostProductiveDay']}\n"
        f"  Least productive day: {stats['leastProductiveDay']}\n\n"
        f"<b>🏆 Top Activities</b>\n{top_acts}\n\n"
        f"<b>📆 Daily Breakdown</b>\n{daily_lines}\n\n"
    )

    if stats.get("aiInsight"):
        msg += f"<b>🤖 Weekly Insight</b>\n{stats['aiInsight']}"

    return msg


@router.post("/")
@router.post("")
async def send_weekly_summary(x_cron_secret: str = Header(None), db=Depends(get_db)):
    """
    Triggered every Sunday by cron-job.org.

    1. Pull the last 7 daily_snapshots.
    2. Aggregate them into a single weekly_snapshot.
    3. Generate an AI insight from the aggregated data.
    4. Send Telegram message + save to weekly_snapshots collection.
    5. Delete the 7 daily_snapshots that were rolled up.
    """
    print(f"DEBUG: Starting weekly summary. Secret: {x_cron_secret}", flush=True)

    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    # ── Fetch last 7 daily snapshots ─────────────────────────────────────────
    cursor = db.daily_snapshots.find().sort("date", -1).limit(7)
    snapshots = await cursor.to_list(length=7)

    if not snapshots:
        print("DEBUG: No daily snapshots found — skipping weekly rollup.", flush=True)
        return {"sent": False, "reason": "no_daily_snapshots"}

    # Sort oldest → newest for readability
    snapshots = sorted(snapshots, key=lambda s: s["date"])

    week_start = snapshots[0]["date"]
    week_end = snapshots[-1]["date"]

    print(f"DEBUG: Rolling up {len(snapshots)} snapshots: {week_start} → {week_end}", flush=True)

    # ── Aggregate stats ───────────────────────────────────────────────────────
    total_hours = _aggregate_category_hours(snapshots)
    total_tracked = sum(s["stats"]["trackedCount"] for s in snapshots)
    total_pings = sum(s["stats"]["totalPings"] for s in snapshots)
    avg_untracked = (
        round(sum(s["stats"]["untrackedPercent"] for s in snapshots) / len(snapshots))
        if snapshots
        else 0
    )
    top_activities = _top_activities_across_week(snapshots)
    most_productive = _most_productive_day(snapshots)
    least_productive = _least_productive_day(snapshots)

    daily_breakdown = [
        {
            "date": s["date"],
            "deepWorkHours": s.get("hoursPerCategory", {}).get("deep_work", 0),
            "untrackedPercent": s["stats"]["untrackedPercent"],
            "trackedCount": s["stats"]["trackedCount"],
        }
        for s in snapshots
    ]

    # ── AI Insight ────────────────────────────────────────────────────────────
    ai_insight = ""
    try:
        # Build a lightweight pseudo-log list that generate_ai_summary can work with
        pseudo_logs = []
        for snap in snapshots:
            for cat, hrs in snap.get("hoursPerCategory", {}).items():
                pseudo_logs.append({
                    "response": f"{cat} ({hrs}h on {snap['date']})",
                    "category": cat,
                    "timestamp": snap["date"],
                })

        raw = await generate_ai_summary(pseudo_logs, [], [])

        # generate_ai_summary returns the full email-style text — extract a
        # short insight (first 400 chars) for Telegram
        ai_insight = raw[:400].strip() if raw else ""
        print("DEBUG: AI weekly insight generated.", flush=True)
    except Exception as e:
        print(f"DEBUG: AI weekly insight failed: {e}", flush=True)

    weekly_stats = {
        "totalHoursPerCategory": total_hours,
        "totalTrackedPings": total_tracked,
        "totalPings": total_pings,
        "avgUntrackedPercent": avg_untracked,
        "mostProductiveDay": most_productive,
        "leastProductiveDay": least_productive,
        "topActivities": top_activities,
        "dailyBreakdown": daily_breakdown,
        "aiInsight": ai_insight,
        "daysIncluded": len(snapshots),
    }

    # ── Save weekly snapshot (idempotent) ─────────────────────────────────────
    existing = await db.weekly_snapshots.find_one({"weekStart": week_start})
    if not existing:
        await db.weekly_snapshots.insert_one({
            "weekStart": week_start,
            "weekEnd": week_end,
            "generatedAt": datetime.now(timezone.utc),
            "stats": weekly_stats,
        })
        print(f"DEBUG: Saved weekly_snapshot for {week_start} → {week_end}", flush=True)
    else:
        print(f"DEBUG: weekly_snapshot for {week_start} already exists — skipping save.", flush=True)

    # ── Send Telegram ─────────────────────────────────────────────────────────
    tg_msg = _build_weekly_telegram_msg(week_start, week_end, weekly_stats)
    try:
        await send_telegram(tg_msg)
        print("DEBUG: Weekly Telegram message sent.", flush=True)
    except Exception as te:
        print(f"DEBUG: Telegram send failed: {te}", flush=True)

    # ── Delete rolled-up daily snapshots ──────────────────────────────────────
    snapshot_dates = [s["date"] for s in snapshots]
    result = await db.daily_snapshots.delete_many({"date": {"$in": snapshot_dates}})
    print(
        f"DEBUG: Deleted {result.deleted_count} daily_snapshots after weekly rollup.",
        flush=True,
    )

    return {
        "sent": True,
        "weekStart": week_start,
        "weekEnd": week_end,
        "daysRolledUp": len(snapshots),
    }


@router.get("/history")
async def get_weekly_history(db=Depends(get_db)):
    """Return all past weekly snapshots newest first — useful for dashboard."""
    cursor = db.weekly_snapshots.find().sort("weekStart", -1).limit(52)
    snapshots = await cursor.to_list(length=52)
    for s in snapshots:
        s["_id"] = str(s["_id"])
        if isinstance(s.get("generatedAt"), datetime):
            s["generatedAt"] = s["generatedAt"].isoformat()
    return snapshots
