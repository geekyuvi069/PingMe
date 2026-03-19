import os
import asyncio
import google.generativeai as genai
from typing import List, Dict, Any
from services.categorize import categorize as keyword_categorize

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Priority order for models
MODELS = ["gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro"]

async def call_gemini(prompt: str, model_name: str = "gemini-2.0-flash-lite", timeout: float = 10.0) -> str:
    """Helper to call Gemini with timeout and error handling."""
    if not GEMINI_API_KEY:
        return ""
    
    try:
        model = genai.GenerativeModel(model_name)
        # run_in_executor to avoid blocking since genai is sync
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: model.generate_content(prompt)),
            timeout=timeout
        )
        return response.text.strip()
    except Exception as e:
        print(f"DEBUG: Gemini error ({model_name}): {e}")
        return ""

async def categorize_with_ai(response_text: str) -> str:
    """Categorize a ping response using Gemini."""
    if not response_text:
        return "untracked"

    prompt = f"""
    Categorize the following activity description into EXACTLY ONE of these categories:
    deep_work, break, admin, meetings, distracted.

    Activity: "{response_text}"

    Rules:
    - Respond with ONLY the category name.
    - If unsure, use 'deep_work'.
    - 'deep_work' includes studying, coding, reading, learning, researching.
    - 'break' includes food, rest, walk, nap.
    - 'admin' includes email, planning, messages, chores.
    - 'meetings' includes calls, syncs, interviews.
    - 'distracted' includes social media, random browsing, entertainment.
    """

    for model in MODELS[:2]: # Use faster models for categorization
        result = await call_gemini(prompt, model_name=model, timeout=5.0)
        result = result.lower().replace(" ", "_")
        if result in ["deep_work", "break", "admin", "meetings", "distracted"]:
            return result
    
    # Fallback to keyword matching
    return keyword_categorize(response_text)

async def generate_nudge(logs_today: List[Dict], stats_today: Dict) -> str:
    """Generate a single sharp sentence nudge based on today's activity."""
    if len(logs_today) < 3:
        return ""

    activities = [l.get("response") for l in logs_today if l.get("response")]
    if not activities:
        return ""

    prompt = f"""
    Generate a single, sharp, motivational or advisory sentence (max 15 words) based on today's activity log.
    If the user is doing well, encourage them. If they are distracted or stuck in admin/meetings, give a gentle nudge to return to deep work.

    Today's activities: {', '.join(activities)}
    Stats: {stats_today}

    Example outputs:
    - "3 hours of admin — deep work window is closing fast."
    - "4 skips in a row — what's actually blocking you?"
    - "Solid focus since 9am, protect this streak."
    """

    return await call_gemini(prompt, model_name="gemini-2.0-flash-lite", timeout=4.0)

async def generate_ai_summary(logs: List[Dict], agenda: List[Dict], notes: List[Dict], stats: Dict) -> str:
    """Generate a daily insight paragraph (4-6 sentences) for the email summary."""
    if not logs:
        return "Not enough data for an AI insight today. Keep pinging!"

    tracked_logs = [l.get("response") for l in logs if l.get("response")]
    agenda_done = [a.get("content") for a in agenda if a.get("completed")]
    agenda_pending = [a.get("content") for a in agenda if not a.get("completed")]
    
    prompt = f"""
    Write a cohesive, insightful 4-6 sentence paragraph (first-person addressing the user) summarizing their day.
    Reference specific activities from the log and compare time spent on Deep Work vs other categories.
    Be reflective, supportive, and slightly professional.

    Logs: {tracked_logs}
    Stats: {stats}
    Completed Tasks: {agenda_done}
    Pending Tasks: {agenda_pending}
    Notes: {[n.get('content') for n in notes]}
    """

    # Try pro model first for better writing
    for model in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]:
        result = await call_gemini(prompt, model_name=model, timeout=15.0)
        if result:
            return result
    
    return ""

async def generate_weekly_insight(weekly_stats: Dict, daily_breakdown: List[Dict], top_activities: List[str]) -> str:
    """Generate a 3-5 sentence weekly pattern analysis."""
    prompt = f"""
    Analyze the following weekly productivity patterns and provide a 3-5 sentence reflection.
    Identify the most and least productive days, trends in deep work, and recommend one concrete change for next week.

    Weekly Stats: {weekly_stats}
    Daily Summaries: {daily_breakdown}
    Top Activities: {top_activities}
    """

    return await call_gemini(prompt, model_name="gemini-2.0-flash", timeout=15.0)
