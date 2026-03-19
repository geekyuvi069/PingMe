# PingMe — User Flows

## Flow 1: Normal 15-Minute Ping (Extension)

```
cron-job.org fires every 15 min
        ↓
POST https://your-app.onrender.com/api/ping/trigger
header: x-cron-secret: your_secret
        ↓
FastAPI checks sleep window → if sleeping, return early
FastAPI checks pause status → if paused, return early
FastAPI checks lastRespondedAt → if responded within interval, return early
        ↓
Sets pendingPing: true in settings
        ↓
Chrome extension countdown hits 0
        ↓
Browser notification fires: "What are you doing right now?"
        ↓
User clicks → popup opens
        ↓
Popup fetches GET /api/ping/nudge/ in background (4s timeout)
AI nudge sentence appears above input if ≥3 logs today
        ↓
User types "studying RAG concepts", clicks Log It
        ↓
POST /api/ping/respond/ { response, source: "extension" }
        ↓
categorize_with_ai() → "deep_work" (with keyword fallback)
Saved to logs, pendingPing cleared, lastRespondedAt updated
Extension timer resets
```

---

## Flow 2: Skip / Untracked Ping

```
Countdown hits 0 → browser notification fires
        ↓
User clicks Skip in popup
→ POST /api/ping/respond/ { skipped: true }
→ Logged as skipped, timer resets

--- OR ---

User ignores notification entirely
→ Extension timer resets after interval
→ Next trigger fires as normal
→ Untracked gap visible in daily email time log
```

---

## Flow 3: Quick Note Capture

```
Popup open (any time, not just on ping)
        ↓
User types thought in input field
Clicks Note button
        ↓
POST /api/notes/ { content, source: "extension" }
Note saved, status message shows "Note saved ✓"
Input cleared — user stays in popup
```

---

## Flow 4: Agenda from Extension

```
User clicks Agenda button in popup
        ↓
GET /api/agenda/ → items load inline in popup
Checkboxes shown for each item
        ↓
User checks an item
→ PATCH /api/agenda/{id} { completed: true }
        ↓
User types new task in "Add task..." input, clicks +
→ POST /api/agenda/ { content, source: "extension" }
→ List refreshes inline
```

---

## Flow 5: AI Mid-Day Nudge

```
User opens extension popup (any time)
        ↓
popup.js calls GET /api/ping/nudge/ in background
        ↓
FastAPI fetches today's logs, computes category breakdown
Calls generate_nudge() → gemini-2.0-flash-lite (4s timeout)
        ↓
If ≥3 logs exist and AI responds in time:
  → "3 hours of admin — deep work window is closing fast."
  → #ai-nudge div appears above log input

If <3 logs or AI times out:
  → nudge div stays hidden, popup loads normally
```

---

## Flow 6: Pause and Resume

```
POST /api/settings { isPaused: true, pauseDurationMinutes: 120 }
        ↓
All pings silenced for 2 hours
        ↓
Next trigger after pause expires → FastAPI auto-clears isPaused
        ↓
--- OR ---
POST /api/settings { isPaused: false, pauseUntil: null }
→ Pings resume immediately
```

---

## Flow 7: Morning Kickoff

```
cron-job.org fires at sleepEnd time
        ↓
POST /api/ping/trigger detects first ping of the day
(lastMorningMessage != today)
        ↓
Calls carryforward internally:
  Incomplete yesterday items → duplicated with today's date + carriedFrom
        ↓
Fetches today's full agenda
        ↓
Telegram message sent (if Telegram configured):

"Good morning! ☀️

📋 Today's Agenda
  ☐ Finish reading RAG paper   [from yesterday]
  ☐ Review project code        [from yesterday]
  ☐ Watch RLHF lecture

Have a great day!"
```

---

## Flow 8: End of Day Summary Email

```
cron-job.org fires at summaryTime (e.g. 21:00 IST → converted to UTC)
        ↓
POST /api/summary/send
        ↓
FastAPI compiles:
  All logs today (pytz IST midnight → UTC for correct date range)
  Agenda: completed vs incomplete
  Category breakdown (each ping = 15 min)
  All notes from today
  Today's reading stats from reading_logs
        ↓
Calls generate_ai_summary() → Gemini paragraph (with fallback)
        ↓
build_html_email() assembles:
  Hero stat cards
  AI Insight block
  Category progress bars
  Reading section (per-book bars + streak)
  Full time log table
  Agenda recap
  Notes
  Tomorrow's priorities
        ↓
Saves daily_snapshot to MongoDB (includes aiInsight + reading fields)
        ↓
Sends via Resend API
Subject: "PingMe 2026-03-18 | Study: 2h 30m | 📖 3 snippets | 3/5 done"
```

---

## Flow 9: Weekly Rollup (Every Sunday)

```
cron-job.org fires Sunday evening
        ↓
POST /api/summary/weekly
        ↓
Fetches last 7 daily_snapshots
        ↓
Aggregates:
  totalHoursPerCategory
  avgUntrackedPercent
  mostProductiveDay / leastProductiveDay
  topActivities across the week
  reading rollup (snippets, words, streak, per-book deltas)
        ↓
Calls generate_weekly_insight() → Gemini 3–5 sentence paragraph
        ↓
Saves to weekly_snapshots (permanent, never deleted)
DELETES the 7 daily_snapshots
        ↓
Sends weekly email via Resend:
  AI Weekly Insight paragraph
  Category bar chart (Mon–Sun)
  Daily deep work breakdown
  Reading section
  Most/least productive days
```

---

## Flow 10: Upload a Book (PDF)

```
User opens extension → Reading tab
Clicks "Add Book" → Upload PDF option
        ↓
Multipart POST /api/reading/books/upload
        ↓
Backend: PyMuPDF extracts full text
Splits into ~280-word snippets
Saves to books collection:
  { title, snippets: [...], totalSnippets: 142, currentSnippet: 0, isActive: true }
        ↓
Extension refreshes book list
Book appears in Reading tab with "0% · 142 snippets"
```

---

## Flow 11: Add a Book from Open Library

```
User opens extension → Reading tab → "Add Book" → Search
Types "Atomic Habits"
        ↓
GET /api/reading/books/search?query=Atomic+Habits
        ↓
Backend calls Open Library search API (no key needed)
Returns list of candidates with title, author, key
        ↓
User selects book → POST /api/reading/books/add { open_library_key, title, author }
Saved to books collection (no snippets — description/metadata only)
        ↓
Book appears in Reading tab
(For Open Library books without PDF, snippets come from description/preview text available)
```

---

## Flow 12: Daily Reading (Extension)

```
User opens extension → Reading tab
        ↓
GET /api/reading/snippet → round-robins across active books
Current snippet text displayed (~280 words, ~2 min)
Progress shown: "Snippet 34/142 · 23% · ~18 days to finish"
Daily pip tracker: ●○ (1 of 2 done today)
        ↓
User reads → clicks "✓ Done"
        ↓
POST /api/reading/snippet/read { bookId, snippetIndex: 34, isBonus: false }
        ↓
reading_logs entry saved
books.currentSnippet advances to 35
        ↓
Pip tracker updates: ●● (2 of 2 done today)
Next snippet ready for "Read More" (isBonus: true)
```

---

## Flow 13: Reading Nudge in Extension

```
Extension background.js alarm fires at 9AM / 7PM
        ↓
Fetches GET /api/reading/stats → { snippetsRead: 0 }
        ↓
If snippetsRead < 2 AND active books exist:
  Sets chrome.storage.local { pendingRead: true }
        ↓
Next time popup opens:
  Nudge banner appears on main panel:
  "📖 You haven't read today — open Reading tab"
        ↓
User switches to Reading tab → reads snippet → banner clears
```

---

## Flow 14: Auto-Categorization with AI

```
User responds: "watching a tutorial on transformers"
        ↓
categorize_with_ai("watching a tutorial on transformers")
        ↓
Sends to gemini-2.0-flash-lite:
  "Categorize this work activity... Reply with ONLY the category name."
        ↓
Gemini returns: "deep_work"
        ↓
Saved: { category: "deep_work", categorySource: "ai" }

--- FALLBACK ---
If Gemini fails or returns invalid category:
  → falls back to keyword categorize()
  → saved with categorySource: "keyword"
```

---

## Flow 15: Manual Sleep Mode

```
User toggles "Manual Sleep Mode" in extension settings
        ↓
chrome.storage.local { isManualSleep: true }
        ↓
background.js clears pingTimer alarm
Countdown display replaced with rotating motivational line
Badge shows "OFF"
        ↓
User toggles off:
  chrome.storage.local { isManualSleep: false }
  Timer resets, alarms restored
```
