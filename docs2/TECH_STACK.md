# PingMe — Tech Stack

## Overview

PingMe is intentionally lightweight. Every tool chosen to keep cost at $0, complexity low, and the entire project in one language — Python.

---

## Stack at a Glance

| Layer | Tool | Why |
|---|---|---|
| Backend + API | Python + FastAPI | Async, fast, same language throughout |
| Frontend Dashboard | Jinja2 + vanilla JS | No build step, no npm, served directly by FastAPI |
| Database | MongoDB + Motor | Motor is the async MongoDB driver for Python |
| Chrome Extension | Manifest V3, vanilla JS | Persistent countdown, notifications, reading tab |
| Cron Trigger | cron-job.org | Free, hits FastAPI endpoints every 15 min |
| Email Summary | Resend.com | Free tier (3000 emails/month), simple HTTP call |
| Hosting | Render.com | Free tier, keep-alive via cron-job.org ping |
| AI — Categorization | Gemini 2.0 Flash Lite | Cheapest model, ~64 calls/day, free tier |
| AI — Nudge | Gemini 2.0 Flash Lite | 4s hard timeout, silently skipped if slow |
| AI — Daily Insight | Gemini Pro / Flash | Daily email paragraph, model fallback chain |
| AI — Weekly Insight | Gemini 2.0 Flash | Sunday rollup, 3–5 sentence pattern analysis |
| PDF Extraction | PyMuPDF (fitz) | Extract and chunk book text for reading feature |
| Book Search | Open Library API | Free, no key required |

**Total monthly cost: $0. Gemini free tier covers all AI usage at 15-min ping frequency.**

---

## Why Each Choice

### FastAPI
Async (works well with Motor for MongoDB), automatic API docs at `/docs`, serves the HTML dashboard via Jinja2 templates — no separate frontend framework needed.

### Motor (Async MongoDB Driver)
FastAPI is async and Motor matches that. Using PyMongo (sync) inside an async FastAPI app blocks the event loop — Motor avoids that entirely.

### Chrome Extension (Manifest V3)
Replaced the Linux-only `popup.py` + `notify-send` + `zenity` approach. The extension works cross-platform, handles the countdown timer, fires browser notifications, hosts the reading tab UI, and calls the API directly. Users load it unpacked from GitHub.

### Gemini (google-generativeai)
Free tier is sufficient for all AI features at PingMe's usage frequency. Model fallback chain in `services/ai.py` tries cheaper/faster models first and escalates on failure. No OpenAI dependency.

### PyMuPDF (fitz)
Fast PDF text extraction in pure Python. Splits extracted text into ~280-word snippets for the reading feature. One pip package, no external service.

### Open Library API
Completely free book metadata and search — no API key needed. Used as the alternative to PDF upload for adding books.

### cron-job.org
Two roles: (1) hits `/api/ping/trigger` every 15 minutes to fire pings, (2) hits a keep-alive endpoint every 14 minutes to prevent Render free-tier spin-down. Also triggers the daily summary and weekly rollup.

### Render.com
Railway's free tier is one month only. Render's free tier is permanent. FastAPI deploys via `Procfile`. Spin-down is mitigated by cron-job.org keep-alive pings.

### Resend for Email
Clean REST API, no SMTP config, generous free tier. One `httpx.post()` call from Python.

---

## Project Structure

```
pingme/
├── main.py                  ← FastAPI app entry point
├── routers/
│   ├── ping.py              ← /api/ping/trigger, /respond, /status, /nudge
│   ├── agenda.py            ← /api/agenda CRUD + carryforward
│   ├── notes.py             ← /api/notes GET + POST
│   ├── summary.py           ← /api/summary GET + POST /send
│   ├── weekly.py            ← /api/summary/weekly
│   ├── settings.py          ← /api/settings GET + POST
│   └── reading.py           ← /api/reading/* (books, snippets, stats, streak)
├── services/
│   ├── db.py                ← Motor MongoDB connection
│   ├── email.py             ← Resend email sender
│   ├── categorize.py        ← Keyword-based categorizer (fallback)
│   ├── ai.py                ← All Gemini functions: categorize_with_ai,
│   │                           generate_nudge, generate_ai_summary,
│   │                           generate_weekly_insight
│   └── pdf_extractor.py     ← PyMuPDF text extraction + snippet splitting
├── templates/
│   ├── dashboard.html       ← Today's timeline, notes, agenda
│   └── settings.html        ← Settings form
├── static/
│   └── style.css            ← Minimal dark theme CSS
├── extension/
│   ├── manifest.json        ← Chrome Manifest V3
│   ├── background.js        ← Countdown alarms, badge, reading nudge alarms
│   ├── popup.html           ← Main panel + reading tab
│   ├── popup.js             ← Log, skip, note, agenda, reading, nudge fetch
│   └── popup.css            ← Dark theme styles incl. #ai-nudge, reading tab
├── .env                     ← Environment variables (never committed)
├── .env.example             ← Template
├── requirements.txt
├── Procfile                 ← For Render deployment
└── Dockerfile               ← Optional, for local Docker use
```

---

## requirements.txt

```txt
fastapi
uvicorn
motor
python-dotenv
httpx
jinja2
pytz
google-generativeai
PyMuPDF
```

---

## Environment Variables

```env
# MongoDB
MONGODB_URI=mongodb+srv://your-connection-string
MONGODB_DB=pingme

# Email (Resend)
RESEND_API_KEY=your_resend_key
SUMMARY_EMAIL=you@gmail.com

# App
APP_URL=https://your-app.onrender.com
CRON_SECRET=make_up_a_random_string_here

# AI
GEMINI_API_KEY=your_gemini_key
```

---

## AI Functions in services/ai.py

| Function | Model | Purpose | Called from |
|---|---|---|---|
| `generate_ai_summary()` | gemini-pro / flash | Daily email insight paragraph | `summary.py` |
| `categorize_with_ai()` | gemini-2.0-flash-lite | Categorize ping response | `ping.py` |
| `generate_nudge()` | gemini-2.0-flash-lite | Mid-day popup nudge sentence | `ping.py /nudge/` |
| `generate_weekly_insight()` | gemini-2.0-flash | Weekly pattern analysis | `weekly.py` |

All functions share the same model fallback pattern — try cheapest first, escalate on failure, fall back to non-AI if all fail.

---

## How the 15-Minute Ping Works End-to-End

```
1. cron-job.org fires every 15 min
        ↓
2. POST https://your-app.onrender.com/api/ping/trigger
   with header: x-cron-secret: your_secret
        ↓
3. FastAPI checks: sleep window? paused? already responded?
        ↓ (if ping should fire)
4. Sets pendingPing: true in MongoDB settings
5. Sends Telegram morning kickoff (first ping of day) or skips
        ↓
6. Chrome extension countdown hits 0
        ↓
7. Browser notification fires
   User clicks → popup opens
        ↓
8. Popup fetches /api/ping/nudge/ (4s timeout, shows AI sentence if ready)
        ↓
9. User types response, clicks Log It
        ↓
10. POST /api/ping/respond/ → categorize_with_ai() → saved to MongoDB logs
    pendingPing cleared, lastRespondedAt updated
```

---

## Deployment Architecture

```
Your Browser (Chrome Extension)  ←──────→  Render.com (FastAPI)
                                            ↑        ↑
                              cron-job.org ─┘        │
                              (ping trigger,          │
                               keep-alive,            │
                               daily summary,         │
                               weekly rollup)         │
                                                 MongoDB Atlas
```

cron-job.org does all scheduling. The extension handles all local UI. Render hosts the API. No local scripts need to be always running.
