# PingMe — Data Models

## MongoDB Collections

PingMe uses 5 collections. All simple, no complex relationships. The `logs` collection gains extra fields as AI phases are introduced — existing data is never broken.

---

## 1. `logs`

Every ping response (or skipped/untracked ping) stored here.

```json
{
  "_id": "ObjectId",
  "timestamp": "2026-02-26T14:30:00Z",
  "response": "studying about RAG and how chunking works",
  "source": "desktop | telegram",
  "skipped": false,
  "untracked": false,
  "category": "deep_work",
  "categorySource": "keyword | embedding | manual",
  "embedding": null
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | Date | Exact time of the ping |
| `response` | String | What the user typed (null if skipped/untracked) |
| `source` | String | Where response came from — desktop or telegram |
| `skipped` | Boolean | User clicked Skip |
| `untracked` | Boolean | Popup ignored and auto-closed |
| `category` | String | Auto-assigned — deep_work, break, admin, meetings, distracted |
| `categorySource` | String | How category was assigned — keyword, embedding, or manual |
| `embedding` | Array | Vector embedding of response text (Phase 3, null until then) |

---

## 2. `notes`

Quick thought captures. Unstructured, no checkboxes, no carry-forward.

```json
{
  "_id": "ObjectId",
  "timestamp": "2026-02-26T15:45:00Z",
  "content": "read about attention mechanism and positional encoding",
  "source": "desktop | telegram | dashboard"
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | Date | When the note was captured |
| `content` | String | The note text |
| `source` | String | Where it was written from |

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
  "source": "desktop | telegram | dashboard"
}
```

| Field | Type | Description |
|---|---|---|
| `content` | String | The task description |
| `completed` | Boolean | Whether it's done |
| `completedAt` | Date | When marked complete (null if not) |
| `createdAt` | Date | When originally created |
| `date` | String | Which day this task belongs to (YYYY-MM-DD) |
| `carriedFrom` | String | Original date if carried forward, null if created today |
| `source` | String | Where it was added from |

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
  "telegramChatId": "123456789",
  "email": "you@gmail.com",
  "isPaused": false,
  "pauseUntil": null,
  "pendingPing": false,
  "pendingPingAt": null,
  "lastRespondedAt": null,
  "updatedAt": "2026-02-26T10:00:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `sleepStart` | String | Time to start silencing pings (HH:MM) |
| `sleepEnd` | String | Time to resume pings (HH:MM) |
| `timezone` | String | Your local timezone |
| `intervalMinutes` | Number | Ping frequency in minutes (default 15) |
| `summaryTime` | String | When to send end of day summary (HH:MM) |
| `telegramChatId` | String | Your Telegram chat ID for the bot |
| `email` | String | Where to send the email summary |
| `isPaused` | Boolean | Whether pings are currently paused |
| `pauseUntil` | Date | Auto-resume time if `/pause 2h` used (null = manual resume) |
| `pendingPing` | Boolean | Whether a ping is waiting for response (popup.py polls this) |
| `pendingPingAt` | Date | When the current pending ping was triggered |
| `lastRespondedAt` | Date | When user last responded — used to avoid double pings |

---

## 5. `insights`

Stores weekly AI-generated insights. Added in Phase 2.

```json
{
  "_id": "ObjectId",
  "weekStart": "2026-02-23",
  "weekEnd": "2026-02-29",
  "generatedAt": "2026-02-26T21:00:00Z",
  "insight": "Your deep work mostly happens 9AM–12PM. After 3PM you're mostly fragmented. Tuesday was your least focused day. Deep work time: 34% — up from 28% last week.",
  "stats": {
    "deepWorkHours": 12.5,
    "fragmentedHours": 8.0,
    "untrackedPercent": 18,
    "mostProductiveDay": "Monday",
    "mostCommonCategory": "deep_work",
    "topActivity": "studying RAG concepts"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `weekStart` | String | Monday of the week (YYYY-MM-DD) |
| `weekEnd` | String | Sunday of the week (YYYY-MM-DD) |
| `generatedAt` | Date | When the insight was generated |
| `insight` | String | Plain-English AI-generated observation |
| `stats` | Object | Raw computed stats that fed into the insight |

---

## Indexes to Create

```javascript
// logs — fetch today's entries fast
db.logs.createIndex({ timestamp: -1 })

// logs — fetch by category for insights
db.logs.createIndex({ category: 1, timestamp: -1 })

// agenda — fetch by date and status fast
db.agenda.createIndex({ date: 1, completed: 1 })

// notes — fetch today's notes fast
db.notes.createIndex({ timestamp: -1 })

// insights — fetch latest weekly insight
db.insights.createIndex({ weekStart: -1 })
```

---

## Default Settings Document

Insert this once when you first set up the project:

```python
await db.settings.insert_one({
    "userId": "default",
    "sleepStart": "02:00",
    "sleepEnd": "10:00",
    "timezone": "Asia/Kolkata",
    "intervalMinutes": 15,
    "summaryTime": "21:00",
    "telegramChatId": "",
    "email": "",
    "isPaused": False,
    "pauseUntil": None,
    "pendingPing": False,
    "pendingPingAt": None,
    "lastRespondedAt": None,
})
```
