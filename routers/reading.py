from fastapi import APIRouter, Depends, Body, HTTPException, UploadFile, File, Form
from services.db import get_db
from services.pdf_extractor import process_pdf, process_epub
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId
import httpx

router = APIRouter(prefix="/api/reading", tags=["reading"])

async def get_active_books(db):
    """Utility to get up to 3 active books."""
    cursor = db.books.find({"isActive": True, "isCompleted": False})
    return await cursor.to_list(length=3)

@router.get("/books")
async def list_books(db = Depends(get_db)):
    """List all books with their progress."""
    cursor = db.books.find().sort("addedAt", -1)
    books = await cursor.to_list(length=100)
    for b in books:
        b["_id"] = str(b["_id"])
        if "snippets" in b:
            del b["snippets"] # Don't send all text to client
    return books

@router.post("/books/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(None),
    db = Depends(get_db)
):
    """Upload a PDF/EPUB, extract clean snippets, and save as a new book."""
    ext = file.filename.split(".")[-1].lower()
    if ext not in ["pdf", "epub"]:
        raise HTTPException(status_code=400, detail="Only PDF and EPUB files are supported")
    
    content = await file.read()
    
    # Use the new improved extraction pipeline
    if ext == "pdf":
        result = await process_pdf(content)
    else:
        result = await process_epub(content)
        
    snippets = result.get("snippets", [])
    content_start = result.get("suggested_start", 0)
    
    if not snippets:
        raise HTTPException(status_code=400, detail="Could not extract text from file")
    
    # Check current active count
    active_count = await db.books.count_documents({"isActive": True})
    
    book = {
        "title": title,
        "author": author or "Unknown",
        "source": ext,
        "snippets": snippets,
        "totalSnippets": len(snippets),
        "currentSnippet": content_start, # Start from real content
        "contentStartIndex": content_start, # Store for reference
        "isActive": active_count < 3,
        "isCompleted": False,
        "addedAt": datetime.now(timezone.utc),
        "completedAt": None
    }
    
    inserted = await db.books.insert_one(book)
    return {"status": "success", "id": str(inserted.inserted_id), "snippets": len(snippets), "start_at": content_start}

@router.post("/books/search")
async def search_open_library(q: str):
    """Search Open Library for book candidates."""
    # Note: Open Library search is free and no-key
    url = f"https://openlibrary.org/search.json?q={q}&limit=5"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json()
        
    results = []
    for doc in data.get("docs", []):
        results.append({
            "title": doc.get("title"),
            "author": doc.get("author_name", ["Unknown"])[0],
            "key": doc.get("key"),
            "cover_id": doc.get("cover_i")
        })
    return results

@router.patch("/books/{book_id}/activate")
async def set_book_active(book_id: str, active: bool = Body(embed=True), db = Depends(get_db)):
    """Toggle a book's active status. Max 3 active."""
    if active:
        active_count = await db.books.count_documents({"isActive": True, "_id": {"$ne": ObjectId(book_id)}})
        if active_count >= 3:
            raise HTTPException(status_code=400, detail="Maximum 3 books can be active at once")
    
    await db.books.update_one({"_id": ObjectId(book_id)}, {"$set": {"isActive": active}})
    return {"status": "success"}

@router.delete("/books/{book_id}")
async def delete_book(book_id: str, db = Depends(get_db)):
    """Delete a book and its snippets."""
    await db.books.delete_one({"_id": ObjectId(book_id)})
    return {"status": "success"}

@router.get("/snippet")
async def get_next_snippet(db = Depends(get_db)):
    """Serve the next snippet from an active book in round-robin fashion."""
    active_books = await get_active_books(db)
    if not active_books:
        return {"snippet": None, "reason": "no_active_books"}
    
    # Simple round-robin: pick the book that hasn't been read from for the longest time
    # based on reading_logs, or just pick the first one with a pending snippet.
    # Logic: find latest read_log for each book.
    
    best_book = None
    last_read_time = datetime.max.replace(tzinfo=timezone.utc)
    
    for book in active_books:
        last_log = await db.reading_logs.find_one({"bookId": book["_id"]}, sort=[("readAt", -1)])
        read_at = last_log["readAt"] if last_log else datetime.min.replace(tzinfo=timezone.utc)
        
        if read_at < last_read_time:
            last_read_time = read_at
            best_book = book
            
    if not best_book:
        best_book = active_books[0]
        
    idx = best_book["currentSnippet"]
    if idx >= best_book["totalSnippets"]:
        # Mark as completed and find another
        await db.books.update_one({"_id": best_book["_id"]}, {"$set": {"isCompleted": True, "isActive": False, "completedAt": datetime.now(timezone.utc)}})
        return await get_next_snippet(db)
        
    snippet = best_book["snippets"][idx]
    
    return {
        "bookId": str(best_book["_id"]),
        "title": best_book["title"],
        "snippetIndex": idx,
        "totalSnippets": best_book["totalSnippets"],
        "content": snippet,
        "pct": int((idx / best_book["totalSnippets"]) * 100)
    }

@router.get("/snippet/{book_id}")
async def get_book_snippet(book_id: str, db = Depends(get_db)):
    """Serve the next snippet from a specific book."""
    book = await db.books.find_one({"_id": ObjectId(book_id)})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    idx = book["currentSnippet"]
    if idx >= book["totalSnippets"]:
        return {"snippet": None, "reason": "completed"}
        
    snippet = book["snippets"][idx]
    
    return {
        "bookId": str(book["_id"]),
        "title": book["title"],
        "snippetIndex": idx,
        "totalSnippets": book["totalSnippets"],
        "content": snippet,
        "pct": int((idx / book["totalSnippets"]) * 100)
    }

@router.post("/snippet/read")
async def mark_read(data: Dict[str, Any] = Body(...), db = Depends(get_db)):
    """Mark a snippet as read, advance progress."""
    book_id = data.get("bookId")
    snippet_idx = data.get("snippetIndex")
    is_bonus = data.get("isBonus", False)
    
    book = await db.books.find_one({"_id": ObjectId(book_id)})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    # Log the read
    log = {
        "bookId": ObjectId(book_id),
        "bookTitle": book["title"],
        "snippetIndex": snippet_idx,
        "readAt": datetime.now(timezone.utc),
        "wordsRead": 280, # Hardcoded per docs
        "isBonus": is_bonus
    }
    await db.reading_logs.insert_one(log)
    
    # Advance currentSnippet
    new_idx = snippet_idx + 1
    update = {"currentSnippet": new_idx}
    if new_idx >= book["totalSnippets"]:
        update["isCompleted"] = True
        update["isActive"] = False
        update["completedAt"] = datetime.now(timezone.utc)
        
    await db.books.update_one({"_id": ObjectId(book_id)}, {"$set": update})
    
    return {"status": "success", "completed": update.get("isCompleted", False)}

@router.get("/stats")
async def get_reading_stats(db = Depends(get_db)):
    """Get today's reading stats."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    cursor = db.reading_logs.find({"readAt": {"$gte": today_start}})
    logs = await cursor.to_list(length=100)
    
    snippets_read = len(logs)
    words_read = sum(l.get("wordsRead", 280) for l in logs)
    books_read = list(set(l.get("bookTitle") for l in logs if l.get("bookTitle")))
    
    # Progress for active books
    active_books = await db.books.find({"isActive": True}).to_list(length=3)
    book_progress = {}
    for b in active_books:
        book_progress[b["title"]] = {
            "current": b["currentSnippet"],
            "total": b["totalSnippets"],
            "pct": int((b["currentSnippet"] / b["totalSnippets"]) * 100) if b["totalSnippets"] > 0 else 0
        }
        
    return {
        "snippetsRead": snippets_read,
        "wordsRead": words_read,
        "booksRead": books_read,
        "bookProgress": book_progress
    }

@router.get("/streak")
async def get_streak(db = Depends(get_db)):
    """Calculate current and longest reading streaks."""
    # Get all unique dates where something was read
    pipeline = [
        {"$project": {"date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$readAt"}}}},
        {"$group": {"_id": "$date"}},
        {"$sort": {"_id": -1}}
    ]
    cursor = db.reading_logs.aggregate(pipeline)
    dates = [d["_id"] for d in await cursor.to_list(length=1000)]
    
    if not dates:
        return {"current": 0, "longest": 0}
        
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    current_streak = 0
    if dates[0] == today_str or dates[0] == yesterday_str:
        # Check current streak
        check_date = datetime.now(timezone.utc)
        date_set = set(dates)
        
        # If last read was today or yesterday, start counting
        while check_date.strftime("%Y-%m-%d") in date_set:
            current_streak += 1
            check_date -= timedelta(days=1)
    
    # Longest streak calculation
    longest_streak = 0
    temp_streak = 0
    prev_date = None
    
    # Iterate dates from oldest to newest to find max gap-free range
    sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d") for d in dates])
    for d in sorted_dates:
        if prev_date is None or (d - prev_date).days == 1:
            temp_streak += 1
        else:
            temp_streak = 1
        prev_date = d
        longest_streak = max(longest_streak, temp_streak)
        
    return {"current": current_streak, "longest": longest_streak}
