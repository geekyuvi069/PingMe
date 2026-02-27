import os
import httpx
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SUMMARY_EMAIL = os.getenv("SUMMARY_EMAIL")

async def send_email(subject: str, html: str):
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": "PingMe <onboarding@resend.dev>",  # Using default resend domain for now
        "to": [SUMMARY_EMAIL],
        "subject": subject,
        "html": html
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
