import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "pingme")

client = None

def get_db():
    global client
    if client is None:
        client = AsyncIOMotorClient(MONGODB_URI)
    return client[MONGODB_DB]
