# PingMe — Features

## 1. Pinging System

- Pings every 15 minutes (interval customizable from settings)
- Desktop notification appears first on Linux
- If no response from desktop within the ping window, Telegram sends the same question
- Free text response — type naturally, no categories or dropdowns
- Ignored pings automatically logged as "untracked"
- Sleep window silences all pings during set hours (e.g. 2AM–10AM)

---

## 2. Desktop Popup (Linux — Python Script)

A native system notification appears in the corner of your screen every 15 minutes, followed by a clean GTK input dialog.

**Uses:** `notify-send` (system notification) + `zenity` (input dialog) — both pre-installed on Ubuntu/Fedora. No extra pip packages needed for the GUI.

**Flow:**
1. `notify-send` fires — system notification appears top-right
2. User clicks — `zenity` input dialog opens
3. User types what they're doing and picks an action

**Four actions in the dialog:**

| Action | What happens |
|---|---|
| OK / Send | Submits activity log, dialog closes |
| Skip | Logs ping as untracked, dialog closes |
| Note | Saves typed text as a quick note (not a log), dialog closes |
| Agenda | Opens zenity list dialog with today's tasks and checkboxes |

**Behaviour:**
- Auto-closes after 2 minutes if ignored → logged as untracked
- Runs on Linux startup via systemd user service or autostart file
- Respects sleep window — does not appear during set hours
- Polls `/api/ping/status` every 60 seconds in background

---

## 3. Telegram Bot (Full Mobile Experience)

No mobile app. Your Telegram bot is your entire phone-side experience.

**Commands:**

| Command | What it does |
|---|---|
| `/agenda` | Shows today's task list with inline ✅ tap-to-complete buttons and ➕ add new item |
| `/pause` | Stops all pings. Optional duration e.g. `/pause 2h` |
| `/resume` | Restarts pings before pause time expires |
| `/note` | Saves a quick thought — type after the command e.g. `/note read about attention mechanism` |
| `/summary` | Shows your full activity log for today on demand |

**Automatic messages from the bot:**
- **Morning kickoff** — sent when sleep window ends. Good morning + today's full agenda with yesterday's incomplete items already merged in
- **Evening summary** — sent at your chosen time. Full end of day report

**Ping fallback:**
- If you haven't responded via desktop, Telegram sends *"Hey! What are you doing? 👀"*
- Just reply in chat — response is saved as a log entry automatically

---

## 4. Sleep Window

- Set a start and end time during which all pings are silenced
- Configured from the web dashboard settings page
- Example: 2:00 AM to 10:00 AM
- During this window: no desktop popup, no Telegram ping
- Morning kickoff message sent automatically when sleep window ends

---

## 5. Pause / Resume

- `/pause` temporarily stops pings without touching your sleep window
- Optional duration — `/pause 2h` auto-resumes after 2 hours
- `/resume` manually restarts pings before the pause expires
- Pause state stored in MongoDB so it persists if bot restarts

---

## 6. Sticky Notes

A scratchpad for thoughts you don't want to lose.

- Capture from desktop popup — pick Note action in dialog
- Capture from Telegram — `/note your thought here`
- Capture from web dashboard — notes panel input
- Notes are timestamped, saved separately from logs and agenda
- Notes appear in your end of day summary

**Notes are not tasks.** Unstructured captures — things to remember, ideas, links, concepts. No checkboxes, no carry-forward.

---

## 7. Agenda

Your daily committed task list.

- Add from desktop popup agenda dialog, Telegram `/agenda`, or web dashboard
- Each item has a checkbox — tap/click to mark complete
- **Incomplete items auto carry forward to the next day**
- Carried-forward items flagged as "from yesterday"
- Appears in morning kickoff message every day
- Completion recap in end of day summary

---

## 8. Web Dashboard

A simple dark-themed web interface served by FastAPI.

**Pages:**

- **Dashboard (`/`)** — three-column layout:
  - Left: today's timeline — all 15-min log entries with timestamp, response, and category badge
  - Middle: agenda panel with checkboxes, add new item input
  - Right: notes panel with timestamps, add new note input
- **Settings (`/settings`)** — form to update sleep window, ping interval, summary time, email, timezone

No React. No npm. Pure HTML + Jinja2 templates + a little vanilla JS for the live interactions.

---

## 9. End of Day Summary

Sent automatically at your chosen time via **Email + Telegram**.

**Contains:**
- Full time log — every entry for the day with timestamps
- Untracked gaps — periods where you skipped or ignored pings
- Agenda recap — completed ✅ vs incomplete ⏳ items
- Tomorrow's priority list — auto-generated from today's incomplete agenda items
- All sticky notes captured during the day
- AI insight of the day (from Week 2 onwards)

---

## 10. Morning Kickoff Message

Sent via Telegram when your sleep window ends every day.

**Contains:**
- Good morning greeting
- Today's full agenda — yesterday's incomplete items already merged in and flagged
- Motivational nudge based on yesterday's completion rate (Phase 2)

---

## 11. Intelligence Layer (Gradual AI)

AI added in phases — only after real data exists. Never forced, always practical.

### Phase 1 — Auto-Categorization (Week 1, no AI cost)
Keyword matching on free-text responses automatically assigns a category to each log entry.

| Category | Example responses |
|---|---|
| `deep_work` | "studying RAG", "reading paper", "writing code", "building feature" |
| `break` | "making tea", "lunch", "taking a walk", "resting" |
| `meetings` | "on a call", "team sync", "discussion", "interview" |
| `admin` | "checking email", "replying messages", "planning", "reviewing" |
| `distracted` | "scrolling", "YouTube", "random browsing", "social media" |

Categories shown as colored badges in the dashboard and grouped in the summary.

### Phase 2 — Weekly AI Insights (Week 2–3, light AI)
Every Sunday your last 7 days of logs are sent to an LLM. Returns a short plain-English insight:

```
📊 Weekly Insight
Your deep work mostly happens 9AM–12PM.
After 3PM you're mostly fragmented.
Tuesday was your least focused day this week.
Deep work time: 34% — up from 28% last week 📈
```

Cost: a few cents per week at most.

### Phase 3 — Smart Categorization (Later)
Embeddings automatically cluster similar activities. *"Reviewing code"*, *"debugging the API"*, and *"fixing the pipeline bug"* all group as `coding` without any rules defined. You review and confirm clusters — system learns your language.

### Weekly Review Message (Every Sunday via Telegram + Email)
- Deep work hours vs fragmented hours for the week
- Most productive day of the week
- Most common activity category
- Biggest untracked gap day
- One AI-generated observation about your week
- Comparison to previous week where data exists
