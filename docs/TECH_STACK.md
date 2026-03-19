# PingMe — Tech Stack

## Overview

PingMe is intentionally lightweight. Every tool chosen to keep cost at $0, complexity low, and the entire project in one language — Python.

---

## Stack at a Glance

| Layer | Tool | Why |
|---|---|---|
| Backend + API | Python + FastAPI | Same language as bot and extension, async, fast |
| Frontend Dashboard | Jinja2 + vanilla JS | No build step, no npm, served directly by FastAPI |
| Database | MongoDB + Motor | Motor is the async MongoDB driver for Python |
| Chrome Extension | JS + HTML/CSS | Modern 4-button UI with Cyber-Noir aesthetic |
| Reading Habit | PyMuPDF + EbookLib | Extracts snippets from PDF and EPUB for consistent habit-forming |
| Summary Email | Resend.com | Free tier, simple HTTP call with SVG charts |
| Hosting | Fly.io | Alpine-based Docker deployment in the `sin` region |
| AI Intelligence | Gemini 2.0 Flash | Powers categorization, nudges, and weekly insights |

**Total monthly cost: $0 at launch. Cents per week when AI is fully utilized.**

---

## Why Each Choice

### FastAPI
FastAPI is the best Python web framework for this project. It's async (works well with Motor for MongoDB), has automatic API docs at `/docs`, and is simple enough that each endpoint is just a function. It also serves the HTML dashboard via Jinja2 templates — no separate frontend framework needed.

### Motor (Async MongoDB Driver)
FastAPI is async and Motor matches that. Using PyMongo (sync) inside an async FastAPI app blocks the event loop — Motor avoids that problem completely.

### notify-send + zenity
Both come pre-installed on Ubuntu and Fedora desktop. `notify-send` fires a native system notification in the corner of the screen. `zenity` opens a native GTK input dialog. No pip packages needed for the GUI. Uses Python's built-in `subprocess` to call them.

### python-telegram-bot
The most mature and well-documented Telegram bot library for Python. Handles all commands, inline keyboards, and message handling cleanly.

### cron-job.org
FastAPI on Railway can't self-schedule. cron-job.org is a free external service that sends an HTTP POST to your FastAPI endpoints on a schedule. Handles the 15-minute ping trigger and the end-of-day summary.

### Railway.app
Railway supports Python apps natively — just push to GitHub and it deploys. Free tier is enough for this project. Unlike Vercel, Railway runs persistent processes which means if needed in future, you could run the bot there too.

### Resend for Email
Clean REST API, no SMTP config, generous free tier. One `httpx.post()` call from Python is all it takes.

---

## Project Structure

```
pingme/
├── main.py                  ← FastAPI app entry point
├── routers/
│   ├── ping.py              ← /api/ping/trigger, /api/ping/respond, /api/ping/status
│   ├── agenda.py            ← /api/agenda (GET, POST, PATCH, DELETE)
│   ├── notes.py             ← /api/notes (GET, POST)
│   ├── summary.py           ← /api/summary (GET, POST send)
│   ├── settings.py          ← /api/settings (GET, POST)
│   └── insights.py          ← /api/insights/generate (Phase 2)
├── services/
│   ├── db.py                ← Motor MongoDB connection
│   ├── telegram.py          ← Telegram message sender helper
│   ├── email.py             ← Resend email sender helper
│   ├── categorize.py        ← Keyword-based auto-categorizer (Phase 1)
│   └── ai.py                ← AI insight + embedding calls (Phase 2+)
├── templates/
│   ├── dashboard.html       ← Today's timeline, notes, agenda
│   └── settings.html        ← Settings form
├── static/
│   └── style.css            ← Minimal dark theme CSS
├── bot.py                   ← Telegram bot (runs separately)
├── popup.py                 ← Linux desktop popup (runs separately)
├── .env                     ← Environment variables
├── .env.example             ← Template
├── requirements.txt         ← All Python dependencies
└── Procfile                 ← For Railway deployment
```

---

## Requirements.txt

```txt
fastapi
uvicorn
motor
python-dotenv
httpx
jinja2
python-telegram-bot
openai          # Phase 2 only — can leave out at launch
```

---

## Environment Variables (.env)

```env
# MongoDB
MONGODB_URI=mongodb+srv://your-connection-string
MONGODB_DB=pingme

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email (Resend)
RESEND_API_KEY=your_resend_key
SUMMARY_EMAIL=you@gmail.com

# App
APP_URL=https://your-app.fly.dev
CRON_SECRET=make_up_a_random_string_here

# AI
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
```

---

## How the 15-Minute Ping Works End-to-End

```
1. cron-job.org fires every 15 min
        ↓
2. POST https://your-app.railway.app/api/ping/trigger
   with header: x-cron-secret: your_secret
        ↓
3. FastAPI checks: sleep window? paused? already responded?
        ↓ (if ping should fire)
4. Sets pendingPing: true in MongoDB settings
5. Sends Telegram message: "Hey! What are you doing? 👀"
        ↓
6. popup.py (running locally) polls /api/ping/status every 60s
   detects pendingPing: true
        ↓
7. notify-send fires system notification
   User clicks → zenity dialog opens
        ↓
8. User types response, hits OK
        ↓
9. POST /api/ping/respond → saved to MongoDB logs
   pendingPing cleared
```

---

## Deployment Architecture

```
Your Linux Machine                    Railway.app (cloud)
─────────────────────                 ──────────────────────
popup.py  (always running)  ←──────→  FastAPI (main.py)
bot.py    (always running)  ←──────→  MongoDB Atlas
                                      ↑
                            cron-job.org (triggers every 15 min)
```

Your machine runs two Python scripts persistently. The FastAPI backend lives in the cloud and both scripts talk to it via HTTP.
