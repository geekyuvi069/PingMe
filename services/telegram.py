import os
import httpx
from services.db import get_db

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def send_telegram_message(text: str):
    """Helper to send a message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("DEBUG: Telegram credentials missing")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        except Exception as e:
            print(f"DEBUG: Telegram send failed: {e}")

async def send_morning_kickoff(db, today_str: str):
    """Send today's agenda via Telegram."""
    # Fetch today's agenda (including carried forward items)
    cursor = db.agenda.find({"date": today_str})
    items = await cursor.to_list(length=100)
    
    if not items:
        # If no items, skip message or send a simple greeting
        await send_telegram_message("🌅 Good morning! No agenda items for today yet. Make it a great one!")
        return

    message = f"🌅 <b>Good morning!</b>\n\nHere is your agenda for today (<b>{today_str}</b>):\n\n"
    
    for item in items:
        icon = "⏳" if not item.get("completed") else "✅"
        carried = " (from yesterday)" if item.get("carriedFrom") else ""
        message += f"{icon} {item['content']}{carried}\n"
    
    message += "\nStay focused! 🚀"
    
    await send_telegram_message(message)
