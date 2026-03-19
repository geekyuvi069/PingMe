# PingMe — Data Models

## MongoDB Collections

PingMe uses 7 collections. The `logs` collection gains extra fields as AI phases are introduced — existing data is never broken. Book progress lives independently and is never touched by the weekly wipe cycle.

---

## 1. `logs`

Every ping response (or skipped/untracked ping) stored here.

```json
{
  "_id": "ObjectId",
  "timestamp": "2026-02-26T14:30:00Z",
  "response": "studying about RAG and how chunking works",
  "source": "extension",
  "skipped": false,
  "untracked": false,
  "category": "deep_work",
  "categorySource": "ai | keyword | manual",
  "embedding": null
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | Date | Exact time of the ping |
| `response` | String | What the user typed (null if skipped/untracked) |
| `source` | String | Where response came from — extension, dashboard |
| `skipped` | Boolean | User clicked Skip |
| `untracked` | Boolean | Popup ignored / auto-closed |
| `category` | String | Auto-assigned — deep_work, break, admin, meetings, distracted |
| `categorySource` | String | How category was assigned — ai, keyword, or manual |
| `embedding` | Array | Vector embedding of response text (Phase 3, null until then) |

---

## 2. `notes`

Quick thought captures. Unstructured, no checkboxes, no carry-forward.

```json
{
  "_id": "ObjectId",
  "timestamp": "2026-02-26T15:45:00Z",
  "content": "read about attention mechanism and positional encoding",
  "source": "extension | dashboard"
}
```

---

## 3. `agenda`

Daily task list with carry-forward logic.

```json
{
  "_id": "ObjectId",
  "content": "finish reading the RAG paper",
  "completed": false,
  "completedAt": null,
  "createdAt": "2026-02-25T09:00:00Z",
  "date": "2026-02-25",
  "carriedFrom": null,
  "source": "extension | dashboard"
}
```

**Carry-forward logic:** At morning kickoff, any agenda item where `completed: false` and `date` is yesterday gets a new copy created with `date` = today and `carriedFrom` = yesterday.

---

## 4. `settings`

Single document. All user preferences in one place.

```json
{
  "_id": "ObjectId",
  "userId": "default",
  "sleepStart": "02:00",
  "sleepEnd": "10:00",
  "timezone": "Asia/Kolkata",
  "intervalMinutes": 15,
  "summaryTime": "21:00",
  "email": "you@gmail.com",
  "isPaused": false,
  "pauseUntil": null,
  "pendingPing": false,
  "pendingPingAt": null,
  "lastRespondedAt": null,
  "lastMorningMessage": null,
  "updatedAt": "2026-02-26T10:00:00Z"
}
```

---

## 5. `daily_snapshots`

One document per day. Saved by `summary.py` before the daily email is sent. Consumed and deleted by the weekly rollup on Sunday.

```json
{
  "_id": "ObjectId",
  "date": "2026-03-18",
  "study_minutes": 150,
  "category_minutes": {
    "deep_work": 150,
    "break": 45,
    "admin": 30,
    "distracted": 15
  },
  "total_pings": 32,
  "untracked_count": 5,
  "agenda_completed": 3,
  "agenda_total": 5,
  "topActivities": ["studying RAG", "writing code", "reading paper"],
  "aiInsight": "You started strong with 2.5 hours of deep work before 11am...",
  "reading": {
    "snippetsRead": 2,
    "wordsRead": 560,
    "booksRead": ["Atomic Habits"],
    "bookProgress": {
      "Atomic Habits": { "current": 34, "total": 142, "pct": 23 }
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `aiInsight` | String | Gemini-generated paragraph from daily email — new |
| `reading` | Object | Today's reading stats — new |
| `reading.snippetsRead` | Number | Total snippets read today |
| `reading.wordsRead` | Number | Approx words read today |
| `reading.booksRead` | Array | Titles of books read today |
| `reading.bookProgress` | Object | Per-book snapshot: current snippet, total, % |

---

## 6. `weekly_snapshots`

Permanent archive. Written once per week during rollup, **never deleted**.

```json
{
  "_id": "ObjectId",
  "weekStart": "2026-03-11",
  "weekEnd": "2026-03-17",
  "generatedAt": "2026-03-17T21:00:00Z",
  "daysIncluded": 6,
  "totalHoursPerCategory": {
    "deep_work": 12.5,
    "break": 4.0,
    "admin": 6.0,
    "distracted": 2.0
  },
  "avgUntrackedPercent": 18,
  "mostProductiveDay": "Wednesday",
  "leastProductiveDay": "Tuesday",
  "topActivities": ["studying transformers", "coding", "client emails"],
  "aiInsight": "This was a mixed week. Wednesday stood out with 4 hours of deep work...",
  "reading": {
    "totalSnippets": 14,
    "totalWords": 3920,
    "longestStreak": 5,
    "bestReadingDay": "Wednesday",
    "booksProgressed": {
      "Atomic Habits": { "startPct": 20, "endPct": 34, "delta": 14 },
      "Sapiens": { "startPct": 5, "endPct": 12, "delta": 7 }
    }
  }
}
```

---

## 7. `books`

One document per book. Never deleted (unless user removes the book). Book progress is completely independent of the log wipe cycle.

```json
{
  "_id": "ObjectId",
  "title": "Atomic Habits",
  "author": "James Clear",
  "source": "pdf | open_library",
  "open_library_key": "/works/OL...",
  "snippets": ["text chunk 1", "text chunk 2", "..."],
  "totalSnippets": 142,
  "currentSnippet": 34,
  "isActive": true,
  "isCompleted": false,
  "addedAt": "2026-03-01T09:00:00Z",
  "completedAt": null
}
```

| Field | Type | Description |
|---|---|---|
| `source` | String | `pdf` (user uploaded) or `open_library` (fetched) |
| `open_library_key` | String | Open Library work key, null for PDFs |
| `snippets` | Array | All ~280-word text chunks extracted from the book |
| `totalSnippets` | Number | Length of snippets array |
| `currentSnippet` | Number | 0-indexed pointer to next snippet to serve |
| `isActive` | Boolean | Whether this book is in the active reading queue (max 3) |
| `isCompleted` | Boolean | True when `currentSnippet >= totalSnippets` |

---

## 8. `reading_logs`

One document per snippet read. Never wiped.

```json
{
  "_id": "ObjectId",
  "bookId": "ObjectId",
  "bookTitle": "Atomic Habits",
  "snippetIndex": 34,
  "readAt": "2026-03-18T09:15:00Z",
  "wordsRead": 280,
  "isBonus": false
}
```

| Field | Type | Description |
|---|---|---|
| `bookId` | ObjectId | Reference to the `books` collection |
| `snippetIndex` | Number | Which snippet was read |
| `isBonus` | Boolean | True when user clicked "Read More" beyond daily 2 |

---

## Wipe Rules Summary

| Collection | Wiped weekly? |
|---|---|
| `logs` | ✅ Yes — after daily snapshot saved |
| `daily_snapshots` | ✅ Yes — after weekly rollup |
| `weekly_snapshots` | ❌ Never |
| `books` | ❌ Never |
| `reading_logs` | ❌ Never |
| `notes` | ❌ Never (today filter handles display) |
| `agenda` | ❌ Never (date filter handles display) |
| `settings` | ❌ Never |

---

## Indexes

```javascript
// logs — fetch today's entries fast
db.logs.createIndex({ timestamp: -1 })

// logs — fetch by category for insights
db.logs.createIndex({ category: 1, timestamp: -1 })

// agenda — fetch by date and status fast
db.agenda.createIndex({ date: 1, completed: 1 })

// notes — fetch today's notes fast
db.notes.createIndex({ timestamp: -1 })

// daily_snapshots — fetch by date
db.daily_snapshots.createIndex({ date: -1 })

// weekly_snapshots — fetch latest
db.weekly_snapshots.createIndex({ weekStart: -1 })

// reading_logs — fetch today's reads fast
db.reading_logs.createIndex({ readAt: -1 })

// reading_logs — fetch by book
db.reading_logs.createIndex({ bookId: 1, readAt: -1 })

// books — fetch active books
db.books.createIndex({ isActive: 1 })
```
