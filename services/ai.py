import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def generate_ai_summary(logs, agenda, notes) -> str:
    # Use names verified from genai.list_models()
    # Switched to pro-latest as primary since flash is hit with 0-limit quota
    models_to_try = ["gemini-pro-latest", "gemini-1.5-pro", "gemini-flash-latest", "gemini-2.0-flash"]
    last_error = None

    prompt = f"""
    You are summarizing someone's productivity day.
    Write a short warm friendly summary email under 200 words.
    
    Include:
    1. Overview: One-line overview of the day as a bullet point.
    2. Time breakdown: Per category in hours/minutes (skip untracked) as bullet points.
    3. Agenda: X of Y completed, list with ✅ and ⏳ as bullet points.
    4. Notes captured (if any) as bullet points.
    5. Tomorrow's priorities (incomplete items) as bullet points.
    6. Motivational line: One short cute motivational line specific to what they did today.
    
    Do not use bold characters (**). Use bullet points (•) for all sections.
    Do not mention untracked time unless over 40% of the day.
    Warm tone, not corporate. Keep it human.
    
    Logs: {logs}
    Agenda: {agenda}  
    Notes: {notes}
    """

    for model_name in models_to_try:
        try:
            print(f"DEBUG: Trying Gemini model: {model_name}", flush=True)
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(prompt)
            print(f"DEBUG: Successfully used model: {model_name}", flush=True)
            return response.text
        except Exception as e:
            print(f"DEBUG: Model {model_name} failed: {e}", flush=True)
            last_error = e
            continue
            
    raise Exception(f"All Gemini models failed. Last error: {last_error}")
