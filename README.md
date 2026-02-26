# PingMe 🚀

PingMe is a personal productivity tracker designed to help you stay focused, track your time, and manage your daily agenda. It features a FastAPI backend, a Telegram bot for mobile interaction, and a professional Chrome Extension for proactive pings.

## ✨ Features

- **Proactive Pings**: Asks "What are you doing?" at set intervals.
- **Auto-Categorization**: Intelligently categorizes your responses (Deep Work, Break, Admin, etc.).
- **Daily Agenda**: Manage tasks via Telegram or the Web Dashboard.
- **Quick Notes**: Capture thoughts on the go.
- **AI Insights**: (Phase 6) Weekly analysis of your productivity patterns.
- **Daily Summaries**: Receive reports via Telegram and Email.

---

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.11+
- MongoDB Atlas (or local MongoDB)
- Telegram Bot Token & Chat ID
- [Resend.com](https://resend.com) API Key (for emails)

### 1. Configuration

Clone the repository and create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Run with Docker (Recommended)

The easiest way to get started is using Docker Compose:

```bash
docker compose up --build -d
```

This will start:
- **API**: [http://localhost:8000](http://localhost:8000)
- **Telegram Bot**: Runs inside the container, connecting to the API via `http://api:8000`.

### 3. Chrome Extension

The Chrome extension handles the active tracking via a 15-minute countdown and browser-based notifications.

1. Open Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `extension/` folder.

---

## 📂 Documentation

- [Build Guide](docs/BUILD_GUIDE.md) - Step-by-step implementation details.
- [Project Overview](docs/PROJECT_OVERVIEW.md) - Architecture and vision.
- [Tech Stack](docs/TECH_STACK.md) - Deep dive into tools used.
- [Features](docs/FEATURES.md) - Full list of capabilities.
- [Data Models](docs/DATA_MODELS.md) - MongoDB schema details.
- [User Flows](docs/USER_FLOWS.md) - How to interact with the system.

---

## 🚀 Deployment

The project is designed to be deployed on **Railway.app**:

1. Connect your GitHub repo.
2. Add all `.env` variables to Railway's environment settings.
3. Deploy!

---

## 📄 License

MIT
