import asyncio
import os
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def check_data():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB", "pingme")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    
    # Yesterday's date
    yesterday_date = (datetime.now(timezone.utc) - timedelta(days=1))
    yesterday_str = yesterday_date.strftime("%Y-%m-%d")
    yesterday_start = yesterday_date.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)
    
    logs_count = await db.logs.count_documents({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_end}})
    notes_count = await db.notes.count_documents({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_end}})
    agenda_count = await db.agenda.count_documents({"date": yesterday_str})
    
    print(f"Yesterday's Date: {yesterday_str}")
    print(f"Logs count: {logs_count}")
    print(f"Notes count: {notes_count}")
    print(f"Agenda count: {agenda_count}")

if __name__ == "__main__":
    asyncio.run(check_data())
