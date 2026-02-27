import os
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
running_in_docker = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"
APP_URL = "http://api:8000" if running_in_docker else os.getenv("APP_URL", "http://localhost:8000")
CRON_SECRET = os.getenv("CRON_SECRET")

# States for conversation handler
ADD_ITEM = 1

async def api_request(method, endpoint, **kwargs):
    """Universal wrapper for API calls with logging and error handling."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            url = f"{APP_URL}{endpoint}"
            response = await client.request(method, url, timeout=10.0, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"API Error ({e.response.status_code}): {e.response.text}")
            return None
        except Exception as e:
            print(f"Connection Error: {e}")
            return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to PingMe!\n\n"
        "I'll help you track your time and stay on top of your agenda.\n\n"
        "Commands:\n"
        "/agenda - Manage today's tasks\n"
        "/pause - Pause pings (e.g. /pause 2h)\n"
        "/resume - Resume pings\n"
        "/note - Save a quick thought\n"
        "/summary - See today's report"
    )

async def agenda_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = await api_request("GET", "/api/agenda")
    
    if items is None:
        await update.message.reply_text("❌ Could not reach the PingMe API.")
        return

    if not items:
        await update.message.reply_text("Your agenda is empty.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add item", callback_data="add")]]))
        return

    keyboard = []
    text = "<b>📋 Today's Agenda</b>\n\n"
    for i in items:
        status = "✅" if i["completed"] else "☐"
        text += f"{status} {i['content']}\n"
        if not i["completed"]:
            keyboard.append([InlineKeyboardButton(f"✅ Done: {i['content'][:20]}...", callback_data=f"done_{i['_id']}")])
            
    keyboard.append([InlineKeyboardButton("➕ Add item", callback_data="add")])
    await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("done_"):
        item_id = query.data.split("_")[1]
        success = await api_request("PATCH", f"/api/agenda/{item_id}", json={"completed": True})
        if success:
            await query.edit_message_text("Marked as done! Refresh /agenda to see changes.")
        else:
            await query.edit_message_text("❌ Failed to update item.")
        
    elif query.data == "add":
        await query.message.reply_text("What do you want to add to your agenda?")
        return ADD_ITEM

async def add_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text
    success = await api_request("POST", "/api/agenda", json={"content": content, "source": "telegram"})
    if success:
        await update.message.reply_text(f"Added: {content} ✅")
    else:
        await update.message.reply_text("❌ Failed to add item.")
    return ConversationHandler.END

async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    duration = " ".join(context.args) if context.args else "2h"
    
    minutes = 120
    try:
        if duration.endswith("h"):
            minutes = int(duration[:-1]) * 60
        elif duration.endswith("m"):
            minutes = int(duration[:-1])
        else:
            minutes = int(duration)
    except ValueError:
        await update.message.reply_text("❌ Invalid duration. Use '2h' or '30m'.")
        return

    # Post to settings - the server handles the pause logic/timestamp via pauseDurationMinutes
    success = await api_request("POST", "/api/settings", json={"isPaused": True, "pauseDurationMinutes": minutes})
    
    if success:
        await update.message.reply_text(f"🔕 Pings paused for {duration}.")
    else:
        await update.message.reply_text("❌ Failed to update settings.")

async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    success = await api_request("POST", "/api/settings", json={"isPaused": False, "pauseUntil": None})
    if success:
        await update.message.reply_text("🔔 Pings resumed!")
    else:
        await update.message.reply_text("❌ Failed to update settings.")

async def note_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = " ".join(context.args)
    if not content:
        await update.message.reply_text("Usage: /note [your thought]")
        return
        
    success = await api_request("POST", "/api/notes", json={"content": content, "source": "telegram"})
    if success:
        await update.message.reply_text("Note saved 📝")
    else:
        await update.message.reply_text("❌ Failed to save note.")

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating and sending your daily summary... 📊")
    
    success = await api_request("POST", "/api/summary/send", headers={"x-cron-secret": CRON_SECRET})
    
    if success:
        await update.message.reply_text("Summary sent to your email and Telegram! ✅")
    else:
        await update.message.reply_text("❌ Failed to send summary. Check server logs.")

async def handle_ping_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    status = await api_request("GET", "/api/ping/status")
    
    if status and status.get("pending"):
        success = await api_request("POST", "/api/ping/respond", json={"response": text, "source": "telegram"})
        if success:
            await update.message.reply_text("Got it! ✅")
        else:
            await update.message.reply_text("❌ Failed to save response.")
    else:
        await update.message.reply_text("No pending ping. Use /note if you want to save this as a note.")

def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback, pattern="^add$")],
        states={
            ADD_ITEM: [MessageHandler(filters.TEXT & (~filters.COMMAND), add_item_callback)],
        },
        fallbacks=[],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("agenda", agenda_cmd))
    application.add_handler(CommandHandler("pause", pause_cmd))
    application.add_handler(CommandHandler("resume", resume_cmd))
    application.add_handler(CommandHandler("note", note_cmd))
    application.add_handler(CommandHandler("summary", summary_cmd))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_ping_response))
    
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
