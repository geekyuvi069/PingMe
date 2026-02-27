def categorize(response: str) -> str:
    if not response:
        return "untracked"
        
    text = response.lower()
    
    categories = {
        "deep_work": ["study", "studying", "read", "reading", "write", "writing", "code", "coding", "debug", "debugging", "build", "building", "research", "implement", "learn", "paper", "concept", "review"],
        "break": ["tea", "coffee", "food", "lunch", "dinner", "walk", "rest", "break", "nap", "relax"],
        "meetings": ["call", "meeting", "sync", "discussion", "interview", "standup", "zoom"],
        "admin": ["email", "message", "slack", "plan", "planning", "reply", "respond", "check"],
        "distracted": ["scroll", "youtube", "social", "netflix", "browsing", "twitter", "instagram"]
    }
    
    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category
            
    return "deep_work"
