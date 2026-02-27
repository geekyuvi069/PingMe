from fastapi import APIRouter, Depends, Body
from services.db import get_db
from datetime import datetime
from typing import Dict, Any

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "userId": "default",
    "sleepStart": "02:00",
    "sleepEnd": "10:00",
    "timezone": "Asia/Kolkata",
    "intervalMinutes": 15,
    "summaryTime": "21:00",
    "email": "",
    "telegramChatId": "",
    "isPaused": False,
    "pauseUntil": None,
    "pendingPing": False,
    "pendingPingAt": None,
    "lastRespondedAt": None,
    "lastMorningMessage": None,
}

@router.get("/")
async def get_settings(db = Depends(get_db)):
    settings = await db.settings.find_one({"userId": "default"})
    if not settings:
        await db.settings.insert_one(DEFAULT_SETTINGS.copy())
        settings = await db.settings.find_one({"userId": "default"})
    
    # Convert ObjectId to str for JSON serialization
    settings["_id"] = str(settings["_id"])
    return settings

@router.post("/")
async def update_settings(updates: Dict[str, Any] = Body(...), db = Depends(get_db)):
    await db.settings.update_one(
        {"userId": "default"},
        {"$set": {**updates, "updatedAt": datetime.utcnow()}}
    )
    return {"status": "success"}
