import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def generate_ai_summary(logs: list, agenda: list, notes: list, stats: dict) -> str:
    """
    Generate a meaningful plain-English insight about yesterday's productivity.
    Returns a short HTML-safe string to embed in the email.
    """

    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    last_error = None

    # Build a clean readable version of the day for the prompt
    category_breakdown = stats.get("categoryBreakdown", {})
    tracked = stats.get("trackedCount", 0)
    untracked_pct = stats.get("untrackedPercent", 0)
    total = stats.get("totalPings", 0)

    # Time per category (assuming 15 min intervals)
    interval = 15
    time_lines = []
    for cat, count in sorted(category_breakdown.items(), key=lambda x: -x[1]):
        minutes = count * interval
        hours = minutes // 60
        mins = minutes % 60
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        time_lines.append(f"- {cat.replace('_', ' ').title()}: {time_str}")

    # Log responses (what they actually did)
    activities = []
    for log in logs:
        if log.get("response"):
            activities.append(log["response"])
    activities_text = "\n".join(f"- {a}" for a in activities[:30])  # cap at 30

    # Agenda summary
    completed = [i["content"] for i in agenda if i.get("completed")]
    pending = [i["content"] for i in agenda if not i.get("completed")]

    # Notes
    notes_text = "\n".join(f"- {n['content']}" for n in notes) if notes else "None"

    prompt = f"""
You are a personal productivity coach giving a warm, honest, and insightful recap of someone's previous day.

Here is their data:

TRACKED TIME BREAKDOWN:
{chr(10).join(time_lines) if time_lines else "No tracked time"}

UNTRACKED: {untracked_pct}% of the day ({total} total pings)

WHAT THEY ACTUALLY DID (their own words):
{activities_text if activities_text else "No responses logged"}

AGENDA COMPLETED ({len(completed)}/{len(completed) + len(pending)}):
Completed: {", ".join(completed) if completed else "None"}
Incomplete: {", ".join(pending) if pending else "None"}

NOTES THEY CAPTURED:
{notes_text}

Write a SHORT, warm, human insight (4-6 sentences max) covering:
1. What kind of day it was overall (focused? scattered? balanced?)
2. One specific observation about their work pattern based on what they did
3. One honest nudge or encouragement based on incomplete tasks or untracked time
4. One thing to carry into today

Rules:
- Do NOT use bold (**) or markdown
- Do NOT use bullet points
- Write in flowing sentences like a thoughtful friend, not a corporate report
- Be specific — mention actual activities they logged, not generic advice
- Keep it under 100 words
"""

    for model_name in models_to_try:
        try:
            print(f"DEBUG: Trying Gemini model: {model_name}", flush=True)
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(prompt)
            print(f"DEBUG: Successfully used model: {model_name}", flush=True)
            return response.text.strip()
        except Exception as e:
            print(f"DEBUG: Model {model_name} failed: {e}", flush=True)
            last_error = e
            continue

    print(f"DEBUG: All Gemini models failed: {last_error}", flush=True)
    return ""  # Return empty string so email still sends without AI section