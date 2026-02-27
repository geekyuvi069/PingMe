from fastapi import APIRouter, Depends, Body, HTTPException
from services.db import get_db
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from bson import ObjectId

router = APIRouter(prefix="/api/agenda", tags=["agenda"])

@router.get("/")
async def get_agenda(date: str = None, db = Depends(get_db)):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    cursor = db.agenda.find({"date": date}).sort("createdAt", 1)
    items = await cursor.to_list(length=100)
    
    for item in items:
        item["_id"] = str(item["_id"])
    return items

@router.post("/")
async def create_agenda_item(data: Dict[str, Any] = Body(...), db = Depends(get_db)):
    date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    item = {
        "content": data["content"],
        "date": date,
        "completed": False,
        "completedAt": None,
        "createdAt": datetime.now(timezone.utc),
        "carriedFrom": data.get("carriedFrom"),
        "source": data.get("source", "unknown")
    }
    result = await db.agenda.insert_one(item)
    return {"status": "success", "id": str(result.inserted_id)}

@router.patch("/{item_id}")
async def toggle_agenda_item(item_id: str, data: Dict[str, Any] = Body(...), db = Depends(get_db)):
    completed = data.get("completed", False)
    update = {
        "completed": completed,
        "completedAt": datetime.now(timezone.utc) if completed else None
    }
    await db.agenda.update_one({"_id": ObjectId(item_id)}, {"$set": update})
    return {"status": "success"}

@router.delete("/{item_id}")
async def delete_agenda_item(item_id: str, db = Depends(get_db)):
    await db.agenda.delete_one({"_id": ObjectId(item_id)})
    return {"status": "success"}

@router.post("/carryforward")
async def carryforward_agenda(db = Depends(get_db)):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Find incomplete items from yesterday
    cursor = db.agenda.find({"date": yesterday, "completed": False})
    items = await cursor.to_list(length=100)
    
    carried_count = 0
    for item in items:
        # Check if already carried forward to avoid duplicates
        existing = await db.agenda.find_one({
            "content": item["content"],
            "date": today,
            "carriedFrom": yesterday
        })
        if not existing:
            new_item = {
                "content": item["content"],
                "date": today,
                "completed": False,
                "completedAt": None,
                "createdAt": datetime.now(timezone.utc),
                "carriedFrom": yesterday,
                "source": item.get("source", "system")
            }
            await db.agenda.insert_one(new_item)
            carried_count += 1
            
    return {"status": "success", "carried": carried_count}
