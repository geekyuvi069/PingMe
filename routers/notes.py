from fastapi import APIRouter, Depends, Body
from services.db import get_db
from datetime import datetime, timezone
from typing import List, Dict, Any

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.get("/")
async def get_notes(db = Depends(get_db)):
    # Get notes from today (UTC)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = db.notes.find({"timestamp": {"$gte": today_start}}).sort("timestamp", -1)
    notes = await cursor.to_list(length=100)
    
    for note in notes:
        note["_id"] = str(note["_id"])
    return notes

@router.post("/")
async def create_note(data: Dict[str, Any] = Body(...), db = Depends(get_db)):
    note = {
        "content": data["content"],
        "source": data.get("source", "unknown"),
        "timestamp": datetime.now(timezone.utc)
    }
    result = await db.notes.insert_one(note)
    return {"status": "success", "id": str(result.inserted_id)}
