# PingMe — Step by Step Build Guide

Every step is self-contained and testable before moving to the next.
Do not skip steps — each one builds on the last.

---

## PHASE 0 — Setup & Accounts (30 min)

### Step 0.1 — Create accounts
- [ ] **GitHub** — create a private repo called `pingme`
- [ ] **Render.com** — sign up, connect your GitHub account
- [ ] **cron-job.org** — sign up (free)
- [ ] **Resend.com** — sign up (free), verify your email
- [ ] **Google AI Studio** — get a `GEMINI_API_KEY` (free tier)

### Step 0.2 — Prepare MongoDB
```
1. Open MongoDB Atlas dashboard
2. Create a new database called: pingme
3. Create collections: logs, notes, agenda, settings,
   daily_snapshots, weekly_snapshots, books, reading_logs
4. Create indexes (see DATA_MODELS.md)
5. Copy your MongoDB connection string
```

### Step 0.3 — Setup project locally
```bash
mkdir pingme && cd pingme
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn motor python-dotenv httpx jinja2 pytz google-generativeai PyMuPDF
pip freeze > requirements.txt

mkdir -p routers services templates static extension docs
touch routers/__init__.py services/__init__.py

git init
git remote add origin https://github.com/yourusername/pingme
```

### Step 0.4 — Create .env file
```env
MONGODB_URI=mongodb+srv://your-connection-string
MONGODB_DB=pingme
RESEND_API_KEY=your_resend_key
SUMMARY_EMAIL=you@gmail.com
APP_URL=http://localhost:8000
CRON_SECRET=make_up_a_random_string_here
GEMINI_API_KEY=your_gemini_key
```

---

## PHASE 1 — FastAPI Core (2–3 hours)

### Step 1.1 — MongoDB connection (`services/db.py`)
Motor async client, module-level singleton, `get_db()` returns the database instance.

✅ Test: `uvicorn main:app --reload` — no import errors.

### Step 1.2 — Email helper (`services/email.py`)
One async `send_email(subject, html)` that POSTs to Resend API with `RESEND_API_KEY`.

### Step 1.3 — Keyword categorizer (`services/categorize.py`)
`categorize(response: str) -> str` with keyword lists for deep_work, break, meetings, admin, distracted. Returns `deep_work` on no match. **This stays as the AI fallback — do not delete.**

### Step 1.4 — Settings router (`routers/settings.py`)
`GET /api/settings` — seeds defaults if none. `POST /api/settings` — `$set` updates.

✅ Test: `curl http://localhost:8000/api/settings` → default settings JSON.

### Step 1.5 — Ping router (`routers/ping.py`)
- `POST /trigger` — cron secret check, sleep/pause/recent-response guards, sets `pendingPing`, sends morning kickoff or ping message
- `GET /status/` — returns `{pending, askedAt}`
- `POST /respond/` — calls `categorize_with_ai()`, inserts to `logs`, clears `pendingPing`
- `GET /nudge/` — fetches today's logs, calls `generate_nudge()` with 4s `asyncio.wait_for` timeout, returns `{nudge: str}`

✅ Test:
```bash
curl -X POST http://localhost:8000/api/ping/trigger -H "x-cron-secret: your_secret"
curl http://localhost:8000/api/ping/status
curl -X POST http://localhost:8000/api/ping/respond/ \
  -H "Content-Type: application/json" \
  -d '{"response": "studying RAG", "source": "extension"}'
curl http://localhost:8000/api/ping/nudge/
```

### Step 1.6 — Notes router (`routers/notes.py`)
`GET /` — today's notes (UTC midnight filter). `POST /` — saves with timestamp.

### Step 1.7 — Agenda router (`routers/agenda.py`)
CRUD + `POST /carryforward` — copies yesterday's incomplete items to today with `carriedFrom`.

### Step 1.8 — Summary router (`routers/summary.py`)

`GET /` — compile today's logs, notes, agenda, stats.

`POST /send` — full flow:
1. Fetch logs/notes/agenda (use pytz IST midnight → UTC for date range)
2. Compute stats: category_minutes (each ping = 15 min), untracked %, agenda counts
3. Call `generate_ai_summary(logs, agenda, notes, stats)` → `ai_insight`
4. Call `get_today_reading_stats(db)` → reading stats
5. Save `daily_snapshot` (includes `aiInsight` + `reading` fields)
6. Call `build_html_email(...)` passing `ai_insight` and reading stats
7. Send via Resend
8. Return `{sent: true}`

✅ Test: `curl -X POST http://localhost:8000/api/summary/send -H "x-cron-secret: your_secret"`

### Step 1.9 — Weekly router (`routers/weekly.py`)

`POST /api/summary/weekly`:
1. Fetch last 7 `daily_snapshots`
2. Aggregate category hours, untracked %, top activities, reading rollup
3. Call `generate_weekly_insight(weekly_stats, daily_breakdown, top_activities)` → AI paragraph
4. Save to `weekly_snapshots`
5. DELETE the 7 `daily_snapshots`
6. Build weekly HTML email + send via Resend

---

## PHASE 2 — AI Services (1–2 hours)

### Step 2.1 — AI service (`services/ai.py`)

Four functions, all using the Gemini model fallback chain:

**`generate_ai_summary(logs, agenda, notes, stats) -> str`**
Daily email insight. ~200 word warm paragraph referencing actual activities. Models: `gemini-pro-latest → gemini-1.5-pro → gemini-flash-latest → gemini-2.0-flash`.

**`categorize_with_ai(response_text: str) -> str`**
Single-word category response. Models: `gemini-2.0-flash-lite → gemini-1.5-flash`. Falls back to `categorize()` on failure. Validates result is in `{deep_work, break, admin, meetings, distracted, untracked}`.

**`generate_nudge(logs_today, stats_today) -> str`**
One sharp sentence (≤15 words) based on today's pattern. Returns `""` if <3 logs. Models: `gemini-2.0-flash-lite → gemini-1.5-flash`.

**`generate_weekly_insight(weekly_stats, daily_breakdown, top_activities) -> str`**
3–5 sentence weekly analysis. References actual days and activities. Models: `gemini-2.0-flash → gemini-1.5-flash → gemini-1.5-pro`.

✅ Test each function independently before wiring into routers.

---

## PHASE 3 — Reading Feature (2–3 hours)

### Step 3.1 — PDF extractor (`services/pdf_extractor.py`)

```python
import fitz  # PyMuPDF

WORDS_PER_SNIPPET = 280

def extract_and_split(file_bytes: bytes) -> list[str]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    words = full_text.split()
    return [" ".join(words[i:i+WORDS_PER_SNIPPET]) for i in range(0, len(words), WORDS_PER_SNIPPET)]
```

### Step 3.2 — Reading router (`routers/reading.py`)

Prefix: `/api/reading`

| Endpoint | Description |
|---|---|
| `GET /books` | List all books with progress |
| `POST /books/upload` | Multipart PDF → extract → split → save |
| `POST /books/search` | Query Open Library, return candidates |
| `POST /books/add` | Add book from Open Library by key |
| `PATCH /books/{id}/activate` | Toggle active (enforce max 3) |
| `DELETE /books/{id}` | Remove book |
| `GET /snippet` | Round-robin next snippet across active books |
| `POST /snippet/read` | Mark read, advance `currentSnippet`, log to `reading_logs` |
| `GET /stats` | Today's reading: snippetsRead, wordsRead, booksRead, bookProgress |
| `GET /streak` | `{current: N, longest: N}` — consecutive days with ≥1 snippet |

Register in `main.py`: `app.include_router(reading.router)`

✅ Test:
```bash
# Upload a PDF
curl -X POST http://localhost:8000/api/reading/books/upload \
  -F "file=@mybook.pdf" -F "title=Test Book" -F "author=Test Author"

# Get snippet
curl http://localhost:8000/api/reading/snippet

# Mark read
curl -X POST http://localhost:8000/api/reading/snippet/read \
  -H "Content-Type: application/json" \
  -d '{"bookId": "...", "snippetIndex": 0, "isBonus": false}'

# Today's stats
curl http://localhost:8000/api/reading/stats
```

### Step 3.3 — Wire reading into summary (`summary.py`)

Add `get_today_reading_stats(db)` helper. Call it in `send_summary()`. Add reading block to `build_html_email()`. Add `reading` field to `daily_snapshot` save.

Reading block in email:
```
📖 Reading Today
─────────────────────────────
Atomic Habits  ████████░░  34%  (+2 snippets · ~560 words)
               At this pace: ~18 days to finish
Total: 2 snippets · 560 words · 🔥 7-day streak
```

Update subject line:
```
PingMe 2026-03-18 | Study: 2h 30m | 📖 2 snippets | 3/5 done
```

### Step 3.4 — Wire reading into weekly (`weekly.py`)

Add `_aggregate_reading(snapshots)` helper. Include reading rollup in `weekly_snapshot`. Add reading section to weekly email HTML.

---

## PHASE 4 — Chrome Extension (2–3 hours)

### Step 4.1 — `background.js`

- Countdown alarm every 1 minute → update badge
- On alarm: fetch `GET /api/reading/stats` → if `snippetsRead < 2` → set `chrome.storage.local { pendingRead: true }`
- Reading nudge alarms at 9AM and 7PM daily

### Step 4.2 — `popup.html`

Main panel (existing):
- Countdown, log input, Log It / Skip / Note / Agenda buttons
- `#ai-nudge` div above log input (hidden by default)
- Reading nudge banner (shown if `pendingRead: true` and books exist)

Reading tab (new):
- Book switcher (dropdown or cards, max 3 active)
- Snippet display with word count + estimated read time
- Done / Read More buttons
- Progress bar: `34% · Snippet 34/142 · ~18 days to finish`
- Daily pip tracker: ●● 

Settings panel (existing): API URL, interval, sleep window, manual sleep toggle.

### Step 4.3 — `popup.js`

Existing functions (preserve): `submitLog`, `submitNote`, `toggleAgenda`, `fetchAgenda`, `addAgendaItem`, `openSettings`, `saveSettings`.

New functions:
- `loadNudge()` — `GET /api/ping/nudge/` → if `data.nudge` → `showNudge(text)`
- `showNudge(text)` — creates/shows `#ai-nudge` div above `.input-group`
- `loadReadingTab()` — `GET /api/reading/snippet` → render snippet, progress bar, pips
- `markSnippetRead(bookId, snippetIndex, isBonus)` — `POST /api/reading/snippet/read`
- `loadReadingStreak()` — `GET /api/reading/streak` → show streak count

Call `loadNudge()` inside the existing `chrome.storage.local.get()` callback on popup load.

### Step 4.4 — `popup.css`

Add:
```css
#ai-nudge {
    display: none;
    background: linear-gradient(135deg, #0d1b2a, #1a1040);
    border-left: 3px solid #60a5fa;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    color: #93c5fd;
    margin-bottom: 10px;
    line-height: 1.4;
    font-style: italic;
}
```

Reading tab styles: book card, snippet text block, progress bar, pip dots.

### Step 4.5 — `manifest.json`

Add `"http://*/*"` and `"https://*/*"` to `host_permissions` (needed to call Render URL). Or keep domain-specific if you hardcode the Render URL.

---

## PHASE 5 — Deploy to Render (30 min)

### Step 5.1 — Procfile
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Step 5.2 — Push and deploy
```bash
git add .
git commit -m "pingme v2 complete"
git push

# Render dashboard:
# New Web Service → connect GitHub repo
# Build command: pip install -r requirements.txt
# Start command: (from Procfile)
# Add all env variables in Environment tab
```

### Step 5.3 — Set up cron-job.org (4 jobs)

**Job 1 — Keep-alive (every 14 min)**
```
URL: GET https://your-app.onrender.com/
Schedule: */14 * * * *
```

**Job 2 — Ping trigger (every 15 min)**
```
URL: POST https://your-app.onrender.com/api/ping/trigger
Header: x-cron-secret: your_secret
Schedule: */15 * * * *
```

**Job 3 — Daily summary (convert IST to UTC)**
```
URL: POST https://your-app.onrender.com/api/summary/send
Header: x-cron-secret: your_secret
Schedule: 0 15 * * *   (= 9PM IST)
```

**Job 4 — Weekly rollup (Sunday)**
```
URL: POST https://your-app.onrender.com/api/summary/weekly
Header: x-cron-secret: your_secret
Schedule: 0 14 * * 0   (= 7:30PM IST Sunday)
```

### Step 5.4 — Load extension
1. `chrome://extensions/` → Enable Developer Mode
2. Load unpacked → select `extension/` folder
3. Open popup → Settings → set API URL to your Render URL

---

## PHASE 6 — End-to-End Test Checklist

- [ ] Trigger ping via cron-job.org → extension badge shows `!`
- [ ] Open popup → nudge appears after 3+ logs exist
- [ ] Log response → category saved with `categorySource: "ai"` or `"keyword"`
- [ ] Skip → logged as skipped
- [ ] Add agenda item → appears in list
- [ ] Tick agenda item → checkbox updates
- [ ] Add note → appears in dashboard
- [ ] Manual sleep toggle → badge shows OFF, countdown disappears
- [ ] Upload PDF → book appears in Reading tab
- [ ] Mark snippet done → progress advances, pip fills
- [ ] Read 2 snippets → nudge banner clears
- [ ] Daily summary → email received with AI insight + reading section
- [ ] Weekly rollup → weekly email received with AI paragraph + reading delta
- [ ] Render spin-down → keep-alive ping prevents it (check Render logs)

---

## Build Order Summary

```
Phase 0  Setup + accounts              30 min
Phase 1  FastAPI Core (9 routers)      3-4 hrs
Phase 2  AI Services (4 functions)     1-2 hrs
Phase 3  Reading Feature               2-3 hrs
Phase 4  Chrome Extension              2-3 hrs
Phase 5  Deploy + cron jobs            30 min
Phase 6  End-to-end testing            1 hr
──────────────────────────────────────────────
Total    One focused weekend
```
