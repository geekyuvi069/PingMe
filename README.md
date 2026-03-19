# PingMe v2.5 🚀

**PingMe** is an advanced personal productivity tracker and habit-forming system designed for the "Cyber-Noir" minimalist. It combines AI-powered activity logging with a sophisticated reading habit engine and cross-platform notifications.

---

## ✨ Core Features

### 🧠 AI Intelligence (Gemini-Powered)
- **Auto-Categorization**: Intelligently classifies your activity (Deep Work, Break, Admin, Meetings, Distracted, Untracked).
- **AI Nudges**: Receives personalized mid-day nudges based on your actual performance and goals.
- **Daily/Weekly Insights**: Cognitive summaries of your productivity patterns delivered to your inbox.

### 📖 Smart Reading Habit
- **Multi-Format Support**: Upload PDF or EPUB books and track your progress snippet by snippet.
- **Velocity Projections**: Calculates your **7-day average reading speed** to provide accurate "Days to Finish" estimates.
- **Habit Alarms**: Native browser notifications at **9:00 AM** and **7:00 PM** to ensure you hit your daily goals.
- **Progress Pips**: Visual "pips" in the extension header that fill as you hit your daily reading target.

### 🕹️ Cyber-Noir Extension
- **4-Button Dashboard**: Log, Skip, Note, and Agenda in a sleek, high-contrast grid.
- **Pause Mode**: Manually silence pings for deep work sessions or breaks.
- **Reading Hub**: In-app snippet reader with book selector and progress indicators.
- **Nudge Banners**: Real-time alerts if you're falling behind on your reading or logging.

### 📧 Visual Summaries
- **Rich HTML Emails**: Beautiful daily reports with **inline SVG charts** (Pie and Bar charts).
- **Agenda Sync**: See exactly what was completed and what's carrying over to tomorrow.

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.12+
- MongoDB Atlas (or local MongoDB)
- [Resend.com](https://resend.com) API Key (for emails)
- [Google Gemini](https://aistudio.google.com/) API Key (for AI features)

### 1. Configuration
Clone the repository and create a `.env` file:
```bash
cp .env.example .env
# Required: MONGODB_URI, RESEND_API_KEY, GEMINI_API_KEY, TELEGRAM_BOT_TOKEN
```

### 2. Local Execution (Docker)
The recommended way to run PingMe is via Docker Compose:
```bash
docker compose up --build -d
```
- **API/Dashboard**: [http://localhost:8000](http://localhost:8000)

### 3. Chrome Extension
1. Open `chrome://extensions/`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `extension/` folder.
4. Set your **API URL** (and [ngrok](https://ngrok.com/) link if using remotely) in the extension settings (⚙).

---

## 🚀 Deployment (Fly.io)

PingMe is optimized for **Fly.io**:
1. Install [flyctl](https://fly.io/docs/hands-on/install-flyctl/).
2. Run `fly launch` (uses existing `fly.toml`).
3. Set secrets:
   ```bash
   fly secrets set MONGODB_URI="..." GEMINI_API_KEY="..." # and others
   ```
4. Deploy: `fly deploy`.

---

## 📄 License
MIT
