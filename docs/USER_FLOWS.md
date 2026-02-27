# PingMe — User Flows

## Flow 1: Normal 15-Minute Ping (Desktop)

```
cron-job.org fires every 15 min
        ↓
POST https://your-app.railway.app/api/ping/trigger
header: x-cron-secret: your_secret
        ↓
FastAPI checks sleep window → if sleeping, return early
FastAPI checks pause status → if paused, return early
FastAPI checks lastRespondedAt → if responded within interval, return early
        ↓
Sets pendingPing: true in settings
        ↓
popup.py (running locally, polling every 60s) detects pendingPing: true
        ↓
subprocess: notify-send "PingMe" "What are you doing?"
        ↓
User clicks notification
        ↓
subprocess: zenity --entry dialog opens
        ↓
User types "studying RAG concepts", clicks OK
        ↓
POST /api/ping/respond { response, source: "desktop" }
        ↓
FastAPI saves to logs with auto-category
Clears pendingPing, updates lastRespondedAt
```

---

## Flow 2: Missed Desktop Ping → Telegram Fallback

```
Ping triggered → pendingPing: true
        ↓
Popup shows, user is away — auto-closes after 120 seconds
        ↓
popup.py calls POST /api/ping/respond { untracked: true }
        ↓
Telegram bot sends: "Hey! What are you doing? 👀"
        ↓
User replies in Telegram: "was making tea, back now"
        ↓
Bot calls POST /api/ping/respond { response, source: "telegram" }
        ↓
Saved to logs, pendingPing cleared
```

---

## Flow 3: Quick Note Capture (Desktop)

```
zenity ping dialog is open
        ↓
User clicks [Note] button
        ↓
New zenity --entry: "What do you want to note?"
User types: "read about positional encoding tomorrow"
        ↓
POST /api/notes { content, source: "desktop" }
Note saved, note dialog closes
        ↓
Original ping dialog still open — user responds to ping normally

> Note action does NOT close or answer the ping. They are separate.
```

---

## Flow 4: Agenda from Desktop

```
zenity ping dialog open
        ↓
User clicks [Agenda]
        ↓
GET /api/agenda → fetches today's items
        ↓
zenity --checklist shows:
  ☐ Finish reading RAG paper
  ☐ Review project code
  ✅ Watch attention lecture
        ↓
User checks "Finish reading RAG paper"
        ↓
PATCH /api/agenda/{id} { completed: true }
        ↓
Checklist closes, ping dialog still open
User responds to ping normally
```

---

## Flow 5: Telegram /agenda Command

```
User types /agenda
        ↓
Bot calls GET /api/agenda
        ↓
Bot replies with inline keyboard:

  📋 Today's Agenda
  ☐ Finish reading RAG paper    [✅ Done]
  ☐ Review project code         [✅ Done]
  ✅ Watch attention lecture
  [➕ Add new item]

        ↓
User taps [✅ Done] next to an item
        ↓
PATCH /api/agenda/{id} { completed: true }
Message edits inline → item shows ✅

        ↓
User taps [➕ Add new item]
Bot: "What do you want to add?"
User: "watch the RLHF lecture"
POST /api/agenda → saved
Bot: "Added ✅"
```

---

## Flow 6: Pause and Resume

```
/pause 1h
        ↓
pauseUntil = now + 1 hour
PATCH /api/settings { isPaused: true, pauseUntil }
Bot: "Paused for 1 hour. Resuming at 4:30 PM 🔕"
        ↓
All pings silenced until 4:30 PM
        ↓
Next trigger after 4:30 PM → FastAPI auto-clears isPaused
Bot: "Pings resumed! What are you doing? 👋"

--- OR ---

/resume → PATCH { isPaused: false, pauseUntil: null }
Bot: "Pings resumed ✅"
```

---

## Flow 7: Morning Kickoff

```
cron-job.org fires at sleepEnd time
        ↓
POST /api/ping/trigger detects sleep window just ended
        ↓
Calls carryforward internally:
  Incomplete yesterday items → duplicated with today's date + carriedFrom
        ↓
Fetches today's full agenda
        ↓
Telegram sends:

"Good morning! ☀️

📋 Today's Agenda
  ☐ Finish reading RAG paper   [from yesterday]
  ☐ Review project code        [from yesterday]
  ☐ Watch RLHF lecture

Have a great day!"
```

---

## Flow 8: End of Day Summary

```
cron-job.org fires at summaryTime
        ↓
POST /api/summary/send
        ↓
FastAPI compiles:
  All logs today (sorted by time)
  Untracked gap count + percentage
  Agenda: completed vs incomplete
  Category breakdown
  All notes from today
  Incomplete items → tomorrow's priorities
        ↓
Telegram message sent:

"📊 Your Day — Feb 26, 2026

⏱️ Time Log
  09:00 — studying RAG concepts        [deep_work]
  09:15 — reading chunking strategies  [deep_work]
  09:30 — [untracked]
  09:45 — making tea                   [break]

📈 Stats
  Deep work: 4.5h  |  Break: 1h  |  Untracked: 18%

📋 Agenda
  ✅ Watch attention lecture
  ⏳ Finish reading RAG paper
  ⏳ Review project code

🗒️ Notes
  • positional encoding — read tomorrow
  • check pinecone vs weaviate

🔜 Tomorrow's Priorities
  • Finish reading RAG paper
  • Review project code"

        ↓
Same data sent as HTML email via Resend
```

---

## Flow 9: Telegram Quick Note

```
/note check how LangChain handles memory buffers
        ↓
POST /api/notes { content, source: "telegram" }
Bot: "Note saved 📝"
        ↓
Appears in dashboard + tonight's summary
```

---

## Flow 10: Auto-Categorization (Phase 1)

```
User responds: "debugging the chunking logic"
        ↓
services/categorize.py runs keyword matching
  "debugging", "logic" → deep_work
        ↓
Saved: { category: "deep_work", categorySource: "keyword" }
        ↓
Dashboard shows green "deep_work" badge
Summary groups it under deep work time
```

---

## Flow 11: Weekly AI Insight (Phase 2)

```
Every Sunday — POST /api/insights/generate
        ↓
Fetch last 7 days of logs
Compute stats: hours per category, untracked %, most active blocks
        ↓
Send stats to OpenAI gpt-4o-mini with prompt asking for
plain-English insight about work patterns
        ↓
Save to insights collection
        ↓
Appended to Sunday summary:

"📊 Weekly Insight
Deep work mostly 9AM–12PM.
After 3PM sessions get fragmented.
Tuesday least focused day (42% untracked).
Deep work: 34% of tracked time — up from 28% 📈"
```

---

## Flow 12: Smart Categorization via Embeddings (Phase 3)

```
User responds: "fixing the memory leak in the pipeline"
        ↓
services/ai.py generates embedding for the text
        ↓
Compares against existing log embeddings in MongoDB
Nearest cluster: "debugging chunking", "fixing RAG pipeline",
"reviewing indexing code" → all deep_work / coding
        ↓
Assigned: { category: "deep_work", categorySource: "embedding" }
        ↓
No keyword rules needed — system learned your language
```
