# PingMe — Project Overview

## What is PingMe?

PingMe is a lightweight personal productivity tracker that checks in with you every 15 minutes asking *"What are you doing?"*. You answer, it saves, and at the end of the day you get a full picture of exactly how you spent your time — broken down by activity, untracked gaps, completed tasks, and tomorrow's priorities.

Built for personal use. No teams, no collaboration, no bloat. Just you, your time, and honest data about how you spend it.

---

## The Problem It Solves

Most people have no idea where their day actually goes. You sit down at 9AM, blink, and it's 6PM. You feel busy but can't account for what you did. PingMe forces a gentle check-in every 15 minutes so your day is always documented — not reconstructed from memory at the end.

---

## How It Works (Simple Version)

1. Every 15 minutes a native system notification appears on your Linux desktop
2. You click it — a small input dialog opens, you type what you're doing, hit OK
3. If you don't respond from desktop, your Telegram bot asks the same question
4. Throughout the day you capture quick notes and manage your daily agenda
5. At night you get a full summary via Email + Telegram
6. Every morning the bot sends your agenda — including anything unfinished from yesterday

---

## Who Is It For?

Built for a single user (you). Runs on Desktop Linux (Ubuntu/Fedora). Backend deployed on Railway.app. Connected to your own MongoDB. Total cost: $0.

---

## The Whole Project Is One Language

Every single piece of PingMe is Python:

```
pingme/
├── main.py       ← FastAPI backend (API + dashboard)
├── bot.py        ← Telegram bot
├── popup.py      ← Linux desktop popup
└── requirements.txt
```

No Node.js. No npm. No build steps. No context switching.

---

## Core Philosophy

- **One language** — Python end to end, simple to understand and maintain
- **Lightweight** — no Electron, no heavy apps, no subscriptions
- **Non-intrusive** — a native notification, 5 seconds to respond, then it's gone
- **Honest** — ignored pings are logged as untracked, not hidden
- **Everything in Telegram** — entire mobile experience is one bot, no app to install
- **Zero friction** — free text responses, no categories to pick, just type and send
- **Gradually intelligent** — AI added on top of real data, never forced from day one

---

## Intelligence Roadmap (Practical AI, Not Heavy AI)

PingMe gets smarter the longer you use it. AI introduced in phases only after real data exists.

**Week 1 — Pattern Math (no AI, zero cost)**
Keyword-based auto-categorization. Basic stats on your most active hours, untracked percentage, and where your time goes.

**Week 2–3 — Light AI (cents per week)**
Last 7 days of logs sent to an LLM once a week. Returns plain-English insights like *"Your deep work mostly happens 9AM–12PM. After 3PM you're mostly fragmented. Tuesday is your worst focus day."* Added to your Sunday summary.

**Later — Smart Categorization**
Embeddings automatically cluster similar activities. *"Reviewing code"*, *"debugging the API"*, *"fixing the pipeline bug"* all become `coding` without you defining any rules.

The goal is never AI for the sake of AI — only insights you couldn't easily see yourself.
