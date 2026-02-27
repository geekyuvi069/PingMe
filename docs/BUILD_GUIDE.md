# PingMe — Step by Step Build Guide

Every step is self-contained and testable before moving to the next.
Do not skip steps — each one builds on the last.

---

## PHASE 0 — Setup & Accounts (30 min)
> Do this once before writing any code.

### Step 0.1 — Create accounts
- [ ] **GitHub** — create a private repo called `pingme`
- [ ] **Railway.app** — sign up, connect your GitHub account
- [ ] **cron-job.org** — sign up (free)
- [ ] **Resend.com** — sign up (free), verify your email or use sandbox

### Step 0.2 — Create your Telegram Bot
```
1. Open Telegram → search @BotFather
2. Send /newbot → follow prompts → name it PingMe
3. Copy the Bot Token (looks like 123456:ABC-DEF...)
4. Start a chat with your new bot, send any message
5. Open in browser:
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
6. Find your chat_id in the JSON — save it
```

### Step 0.3 — Prepare MongoDB
```
1. Open MongoDB Atlas dashboard
2. Create a new database called: pingme
3. Create 5 collections: logs, notes, agenda, settings, insights
4. Create indexes in the MongoDB Atlas UI or shell:
```
```javascript
db.logs.createIndex({ timestamp: -1 })
db.logs.createIndex({ category: 1, timestamp: -1 })
db.agenda.createIndex({ date: 1, completed: 1 })
db.notes.createIndex({ timestamp: -1 })
db.insights.createIndex({ weekStart: -1 })
```
```
5. Copy your MongoDB connection string (mongodb+srv://...)
```

### Step 0.4 — Setup project locally
```bash
mkdir pingme && cd pingme
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn motor python-dotenv httpx jinja2 python-telegram-bot
pip freeze > requirements.txt

mkdir -p routers services templates static
touch routers/__init__.py services/__init__.py

git init
git remote add origin https://github.com/yourusername/pingme
```

### Step 0.5 — Create .env file
```env
MONGODB_URI=mongodb+srv://your-connection-string
MONGODB_DB=pingme
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
RESEND_API_KEY=your_resend_key
SUMMARY_EMAIL=you@gmail.com
APP_URL=http://localhost:8000
CRON_SECRET=make_up_a_random_string_here
OPENAI_API_KEY=
```

### Step 0.6 — Verify Linux popup tools
```bash
notify-send --version && zenity --version

# If missing on Ubuntu:
sudo apt install libnotify-bin zenity

# If missing on Fedora:
sudo dnf install libnotify zenity

# Test they work:
notify-send "PingMe" "Test notification"
zenity --entry --title="PingMe" --text="What are you doing?"
```

✅ Done when both show a visible notification and dialog on your screen.

---

## PHASE 1 — FastAPI Core (2–3 hours)
> Backend only. No UI yet. Test every endpoint with curl before moving on.

### Step 1.1 — MongoDB connection (services/db.py)

**Tell Claude:**
*"Write services/db.py for a FastAPI project. Use Motor (async MongoDB driver) and python-dotenv. Create a get_db() async function that returns the Motor database instance using MONGODB_URI and MONGODB_DB from .env. Use a module-level client so connection is reused across requests."*

✅ Test:
```bash
uvicorn main:app --reload
# No import errors = good
```

---

### Step 1.2 — Telegram + Email helpers

**Tell Claude (telegram):**
*"Write services/telegram.py. One async function send_message(text: str) that sends a message to TELEGRAM_CHAT_ID via the Telegram Bot API using httpx AsyncClient. Uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from .env."*

**Tell Claude (email):**
*"Write services/email.py. One async function send_email(subject: str, html: str) that POSTs to https://api.resend.com/emails using httpx AsyncClient with RESEND_API_KEY auth header. Sends from noreply@yourdomain.com to SUMMARY_EMAIL from .env."*

✅ Test:
```bash
python -c "
import asyncio
from services.telegram import send_message
asyncio.run(send_message('PingMe is alive 👋'))
"
```

---

### Step 1.3 — Auto-categorizer (services/categorize.py)

**Tell Claude:**
*"Write services/categorize.py. A function categorize(response: str) -> str. Categories and their keywords: deep_work (study, studying, read, reading, write, writing, code, coding, debug, debugging, build, building, research, implement, learn, paper, concept, review), break (tea, coffee, food, lunch, dinner, walk, rest, break, nap, relax), meetings (call, meeting, sync, discussion, interview, standup, zoom), admin (email, message, slack, plan, planning, reply, respond, check), distracted (scroll, youtube, social, netflix, browsing, twitter, instagram). Return deep_work if no match. Case insensitive."*

---

### Step 1.4 — Settings router (routers/settings.py)

**Tell Claude:**
*"Write routers/settings.py for FastAPI. APIRouter with prefix /api/settings. GET / returns settings document from MongoDB, seeds defaults if none exists (sleepStart: 02:00, sleepEnd: 10:00, timezone: Asia/Kolkata, intervalMinutes: 15, summaryTime: 21:00, isPaused: false, pauseUntil: null, pendingPing: false, pendingPingAt: null, lastRespondedAt: null, lastMorningMessage: null). POST / accepts a dict and updates settings fields with $set. Use Motor async and get_db()."*

Wire into main.py:
```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from routers import settings, ping, agenda, notes, summary
app = FastAPI()
app.include_router(settings.router)
# add others as you build them
```

✅ Test:
```bash
curl http://localhost:8000/api/settings
# Returns default settings JSON
```

---

### Step 1.5 — Ping router (routers/ping.py)

**Tell Claude:**
*"Write routers/ping.py for FastAPI. APIRouter prefix /api/ping. Three endpoints:

POST /trigger — validate x-cron-secret header vs CRON_SECRET env var, return 403 if wrong. Fetch settings. Check: (1) current time inside sleepStart-sleepEnd in settings.timezone? Return {fired:false, reason:sleep_window}. (2) isPaused true and pauseUntil not passed? Return {fired:false, reason:paused}. If pauseUntil passed, auto-clear isPaused first. (3) lastRespondedAt within intervalMinutes? Return {fired:false, reason:recent_response}. If all pass: update settings pendingPing:true, pendingPingAt:now. Check if current time is within 15 min of sleepEnd and lastMorningMessage != today — if so call carryforward and send morning Telegram message with today's agenda. Otherwise send ping Telegram message. Return {fired:true}.

GET /status — return {pending: bool, askedAt: datetime|null} from settings.

POST /respond — body {response:str, source:str, skipped:bool=false, untracked:bool=false}. If not skipped/untracked, run categorize(response). Insert into logs collection. Update settings: pendingPing:false, lastRespondedAt:now. Return saved log."*

✅ Test:
```bash
curl -X POST http://localhost:8000/api/ping/trigger \
  -H "x-cron-secret: your_secret"
# { "fired": true }

curl http://localhost:8000/api/ping/status
# { "pending": true }

curl -X POST http://localhost:8000/api/ping/respond \
  -H "Content-Type: application/json" \
  -d '{"response": "studying RAG", "source": "desktop"}'
# Check MongoDB logs — entry with category: deep_work
```

---

### Step 1.6 — Notes router (routers/notes.py)

**Tell Claude:**
*"Write routers/notes.py for FastAPI. APIRouter prefix /api/notes. GET / returns all notes where timestamp >= start of today UTC, sorted descending. POST / accepts {content: str, source: str}, saves to notes collection with timestamp:now."*

✅ Test:
```bash
curl -X POST http://localhost:8000/api/notes \
  -H "Content-Type: application/json" \
  -d '{"content": "read about positional encoding", "source": "test"}'

curl http://localhost:8000/api/notes
```

---

### Step 1.7 — Agenda router (routers/agenda.py)

**Tell Claude:**
*"Write routers/agenda.py for FastAPI. APIRouter prefix /api/agenda. Endpoints: GET / returns items where date = today as YYYY-MM-DD string, sorted by createdAt. POST / creates item {content, date:today, completed:false, completedAt:null, createdAt:now, carriedFrom:null, source}. PATCH /{id} toggles completed, sets completedAt:now if completing or null if uncompleting. DELETE /{id} removes item. POST /carryforward finds all items with date=yesterday and completed:false, creates copies with date=today and carriedFrom=yesterday, returns {carried: int}."*

✅ Test:
```bash
curl -X POST http://localhost:8000/api/agenda \
  -H "Content-Type: application/json" \
  -d '{"content": "finish reading RAG paper", "source": "test"}'

curl http://localhost:8000/api/agenda

curl -X PATCH http://localhost:8000/api/agenda/ITEM_ID \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

---

### Step 1.8 — Summary router (routers/summary.py)

**Tell Claude:**
*"Write routers/summary.py for FastAPI. APIRouter prefix /api/summary.

GET / fetches: today's logs sorted by timestamp, today's notes, today's agenda items. Computes stats: totalPings, trackedCount (skipped=false, untracked=false), untrackedCount, untrackedPercent (int), categoryBreakdown (dict category->count). Returns all as compiled dict.

POST /send validates CRON_SECRET header. Calls GET summary logic internally. Formats readable Telegram message (time log with categories, stats line, agenda completed vs incomplete, notes, tomorrow's priorities from incomplete items). Sends via services/telegram.py. Formats HTML email and sends via services/email.py. Returns {sent: true}."*

✅ Test:
```bash
curl http://localhost:8000/api/summary
# Full summary JSON

curl -X POST http://localhost:8000/api/summary/send \
  -H "x-cron-secret: your_secret"
# Check Telegram + email
```

---

## PHASE 2 — Telegram Bot (1–2 hours)

### Step 2.1 — Build bot.py

**Tell Claude:**
*"Write bot.py using python-telegram-bot v20+ (async). Load TELEGRAM_BOT_TOKEN and APP_URL from .env.

/start — welcome message.
/agenda — GET {APP_URL}/api/agenda, show as inline keyboard: each incomplete item gets a [✅ Done] button, completed items show ✅ prefix. Add [➕ Add item] button. Handle callback_query for Done buttons to call PATCH. Handle ➕ with ConversationHandler to get text then POST /api/agenda.
/pause — parse duration from command text (2h, 30m, 1h30m). POST /api/settings with isPaused:true and pauseUntil. Confirm message.
/resume — POST /api/settings {isPaused:false, pauseUntil:null}. Confirm.
/note — text after command saved via POST /api/notes {source:telegram}. Confirm.
/summary — GET /api/summary, format and send as readable message.
Plain text handler — if GET /api/ping/status returns pending:true, POST /api/ping/respond {response:text, source:telegram} and confirm. Otherwise ignore or save as note.

Use httpx.AsyncClient for all API calls."*

✅ Test:
```bash
python bot.py &
# In Telegram:
# /summary → today's summary
# /agenda → items with ✅ buttons
# Tap ✅ → item toggles
# /note read about transformers → confirmed
# /pause 1h → confirmed paused
# /resume → confirmed resumed
```

---

## PHASE 3 — Desktop Popup (1–2 hours)

### Step 3.1 — Build popup.py

**Tell Claude:**
*"Write popup.py for Linux desktop. Uses subprocess for notify-send and zenity. Uses httpx for API calls. Load APP_URL from .env.

Main async loop polling GET {APP_URL}/api/ping/status every 60 seconds.

When pending:true detected:
1. subprocess notify-send 'PingMe' 'What are you doing?'
2. subprocess zenity --entry --title=PingMe --text='What are you doing right now?' --ok-label=Send --extra-button=Skip --extra-button=Note --extra-button=Agenda --timeout=120

Parse zenity result:
- returncode 0, stdout has text → POST /api/ping/respond {response:text.strip(), source:desktop}
- returncode 0, stdout empty → POST /api/ping/respond {skipped:true}
- returncode 1 and 'Skip' in stderr → POST /api/ping/respond {skipped:true}
- returncode 1 and 'Note' in stderr → open second zenity --entry 'What to note?' → POST /api/notes → then show ping dialog again
- returncode 1 and 'Agenda' in stderr → GET /api/agenda → build zenity --checklist with item ids as keys → on selection call PATCH /api/agenda/{id} for each checked item → show ping dialog again
- returncode 5 (timeout) or exception → POST /api/ping/respond {untracked:true}

Run with asyncio.run(). Catch all exceptions, log them, continue loop."*

✅ Test:
```bash
python popup.py &
# In MongoDB Atlas, set settings.pendingPing = true manually
# Within 60s: notification appears → click → dialog opens
# Type something → Send → check MongoDB logs
```

---

### Step 3.2 — Run on startup

**systemd (recommended):**
```bash
mkdir -p ~/.config/systemd/user
```

Create `~/.config/systemd/user/pingme-popup.service`:
```ini
[Unit]
Description=PingMe Desktop Popup
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory=/full/path/to/pingme
ExecStart=/full/path/to/pingme/venv/bin/python popup.py
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable pingme-popup
systemctl --user start pingme-popup
systemctl --user status pingme-popup
```

✅ Test: Log out, log back in. Run `ps aux | grep popup.py` — process should be running.

---

## PHASE 4 — Web Dashboard (2 hours)

### Step 4.1 — Dashboard page

**Tell Claude:**
*"Write templates/dashboard.html as a Jinja2 template for FastAPI. Dark theme: background #0a0a0a, cards #1a1a1a, text white, font monospace. Three columns:

Left — Timeline: list of today's log entries passed from context. Each row: HH:MM time | response text | category badge (deep_work=green, break=cyan, admin=yellow, meetings=purple, distracted=red, untracked=grey).

Middle — Agenda: checkboxes for each item. Clicking calls PATCH /api/agenda/{id} via fetch(). Items with carriedFrom show small [yesterday] tag. Text input + Add button at bottom calls POST /api/agenda.

Right — Notes: list with timestamps. Text input + Save button calls POST /api/notes.

All interactions use vanilla JS fetch(). No frameworks. No external CSS."*

Add to main.py:
```python
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def dashboard(request: Request):
    # fetch summary data and pass to template
    ...
```

---

### Step 4.2 — Settings page

**Tell Claude:**
*"Write templates/settings.html as a Jinja2 template. Same dark theme. Form fields: sleepStart (time input), sleepEnd (time input), intervalMinutes (number), summaryTime (time), email (email), timezone (select: Asia/Kolkata, UTC, US/Eastern, US/Pacific, Europe/London, Europe/Berlin). On submit, fetch POST /api/settings and show success toast. Pre-populate from settings passed in context."*

Add GET `/settings` route in main.py.

✅ Test: `http://localhost:8000` shows dashboard. `http://localhost:8000/settings` shows form, saves correctly.

---

## PHASE 5 — Deploy (30 min)

### Step 5.1 — Procfile
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Step 5.2 — Push and deploy
```bash
git add .
git commit -m "pingme complete"
git push

# Railway dashboard:
# New Project → Deploy from GitHub → select pingme repo
# Variables tab → add all .env variables
# Note your Railway URL after deploy
```

### Step 5.3 — Update APP_URL everywhere
- Railway Variables: `APP_URL=https://your-app.railway.app`
- Local .env: same
- Restart popup.py and bot.py

### Step 5.4 — Set up cron-job.org (3 jobs)

**Job 1 — Ping trigger (every 15 min)**
```
URL: POST https://your-app.railway.app/api/ping/trigger
Header: x-cron-secret: your_secret
Schedule: */15 * * * *
```

**Job 2 — End of day summary (daily)**
```
URL: POST https://your-app.railway.app/api/summary/send
Header: x-cron-secret: your_secret
Schedule: 0 21 * * *  (or your summaryTime)
```

**Job 3 — Weekly AI insight (disabled for now)**
```
URL: POST https://your-app.railway.app/api/insights/generate
Header: x-cron-secret: your_secret
Schedule: 0 20 * * 0  (Sunday 8PM)
Status: DISABLED — enable after 1 week of data
```

✅ Test: Manually trigger Job 1 from cron-job.org. Check Telegram for message. Check MongoDB for pendingPing:true.

---

## PHASE 6 — AI Insights (after 1 week of real data)

> Do not start this until you have 5-7 days of actual logs.

### Step 6.1 — Add OpenAI
```bash
pip install openai
pip freeze > requirements.txt
```
Add to .env and Railway variables: `OPENAI_API_KEY=sk-...`

### Step 6.2 — AI service + insights router

**Tell Claude:**
*"Write services/ai.py with async function generate_weekly_insight(logs: list) -> dict. Computes stats from logs: total hours per category, untracked percent per day, most active time blocks (group by hour), most frequent response texts, most productive day. Sends stats to OpenAI gpt-4o-mini via the openai Python client with a system prompt asking for a 3-4 sentence plain-English insight about work patterns, specific with numbers. Returns {insight: str, stats: dict}."*

**Tell Claude:**
*"Write routers/insights.py for FastAPI. POST /api/insights/generate validates CRON_SECRET. Fetches last 7 days of logs from MongoDB. Calls generate_weekly_insight(). Saves to insights collection with weekStart, weekEnd, generatedAt, insight, stats. Returns the result."*

### Step 6.3 — Add insight to Sunday summary
Update routers/summary.py POST /send: if today is Sunday, fetch latest insight from insights collection and append to both Telegram message and email.

### Step 6.4 — Enable cron job
Go to cron-job.org → enable Job 3.

✅ Test:
```bash
curl -X POST https://your-app.railway.app/api/insights/generate \
  -H "x-cron-secret: your_secret"
# Check MongoDB insights collection for result
```

---

## PHASE 7 — Polish (1 hour)

### Step 7.1 — Error handling
Add try/except to all routers. If MongoDB unreachable return 503. If Telegram fails log it but don't crash trigger. If popup.py can't reach API log and retry next poll.

### Step 7.2 — Full end-to-end checklist
- [ ] Trigger ping via cron-job.org → Telegram message appears
- [ ] Desktop popup appears within 60s → respond → MongoDB log saved
- [ ] Ignore popup → auto-closes → logged as untracked → Telegram fallback fires
- [ ] /agenda → items show with ✅ buttons → tap completes item
- [ ] /note → saves → appears in dashboard
- [ ] /pause 30m → pings stop → auto-resume after 30 min
- [ ] Evening summary → Telegram message + email both received
- [ ] Morning kickoff → agenda with yesterday's items carried forward
- [ ] Settings page → change sleep window → pings respect new window
- [ ] Dashboard → timeline, agenda, notes all show correctly

---

## Build Order Summary

```
Phase 0  Setup + accounts              30 min
Phase 1  FastAPI (8 endpoints)         2-3 hrs
Phase 2  Telegram bot                  1-2 hrs
Phase 3  Desktop popup + startup       1-2 hrs
Phase 4  Web dashboard                 2 hrs
Phase 5  Deploy + cron jobs            30 min
──────────────────────────────────────────────
         Use for 1 week
──────────────────────────────────────────────
Phase 6  AI insights                   1-2 hrs
Phase 7  Polish + full test            1 hr
──────────────────────────────────────────────
Total    1 focused weekend + 1 week data
```

---

## How to Use This Guide With Claude

Every step has a Tell Claude prompt. Use it like this:

> "I'm building PingMe — a personal productivity tracker. Full Python stack: FastAPI + Motor + MongoDB + python-telegram-bot + notify-send/zenity on Desktop Linux. Deployed on Railway. Here is my current project structure: [paste your file tree]. Now build this specific file: [paste the Tell Claude prompt]."

One file per session. Give Claude your current file structure every time so it knows what already exists. Don't dump all docs every session — only paste what's relevant to the step you're on.
