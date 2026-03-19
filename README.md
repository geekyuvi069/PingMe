# PingMe 🚀

- **Proactive Pings**: Track your activity at set intervals via the Web Dashboard.
- **Auto-Categorization**: Intelligently categorizes your responses (Deep Work, Break, Admin, etc.).
- **Daily Agenda**: Manage tasks via the Web Dashboard.
- **Quick Notes**: Capture thoughts on the go.
- **Daily Summaries**: Receive detailed reports via Email.

---

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.11+
- MongoDB Atlas (or local MongoDB)
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
