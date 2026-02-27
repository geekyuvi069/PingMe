import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routers import settings, ping, agenda, notes, summary
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="PingMe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(settings.router)
app.include_router(ping.router)
app.include_router(agenda.router)
app.include_router(notes.router)
app.include_router(summary.router)

@app.post("/test-post")
async def test_post():
    return {"status": "ok"}

@app.get("/")
async def root(request: Request):
    from routers.summary import get_summary
    from services.db import get_db
    db = get_db()
    summary_data = await get_summary(db)
    return templates.TemplateResponse("dashboard.html", {"request": request, "summary": summary_data})

@app.get("/settings")
async def settings_ui(request: Request):
    from routers.settings import get_settings
    from services.db import get_db
    db = get_db()
    settings_data = await get_settings(db)
    return templates.TemplateResponse("settings.html", {"request": request, "settings": settings_data})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
