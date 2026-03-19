import fitz  # PyMuPDF
from ebooklib import epub
from bs4 import BeautifulSoup
import re
import io
import asyncio
from typing import List, Dict, Any
from services.ai import call_gemini

WORDS_PER_SNIPPET = 280

def clean_text(raw_text: str) -> str:
    """
    Cleans raw text by removing headers, footers, TOC patterns, and common junk.
    """
    # Split into lines for preliminary cleaning
    lines = raw_text.splitlines()
    cleaned_lines = []
    
    # Common junk patterns
    junk_patterns = [
        r"(?i)all rights reserved",
        r"(?i)no part of this publication",
        r"(?i)isbn",
        r"(?i)first published",
        r"(?i)printed in",
        r"(?i)dedication",
        r"(?i)acknowledgement",
        r"(?i)foreword",
        r"(?i)table of contents",
        r"(?i)contents",
        r"(?i)index",
        r"(?i)preface"
    ]
    
    # TOC patterns like "Chapter 1 .... 12"
    toc_pattern = re.compile(r".*\.{a,}\s*\d+", re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 1. Remove lines shorter than 4 words (headers, page numbers, etc.)
        if len(line.split()) < 4:
            continue
            
        # 2. Remove lines matching TOC patterns
        if toc_pattern.match(line):
            continue
            
        # 3. Remove lines that are ALL CAPS (usually headers/titles)
        if line.isupper():
            continue
            
        # 4. Remove common junk phrases
        skip = False
        for pattern in junk_patterns:
            if re.search(pattern, line):
                skip = True
                break
        if skip:
            continue
            
        cleaned_lines.append(line)
        
    # Collapse multiple blank lines into single paragraph breaks
    # We join with double newlines to treat original lines as paragraphs for more cleaning
    return "\n\n".join(cleaned_lines)

def find_content_start(paragraphs: list[str]) -> int:
    """
    Identifies the index of the first paragraph that looks like real book content.
    """
    front_matter_words = ["copyright", "isbn", "dedication", "acknowledgement", "foreword", "contents", "index", "preface"]
    
    for i, p in enumerate(paragraphs):
        # A paragraph is "real prose" if it has >= 2 sentences AND >= 20 words
        sentences = re.split(r'[.!?]\s+', p)
        word_count = len(p.split())
        
        if len(sentences) >= 2 and word_count >= 20:
            # Check if it still looks like front matter
            is_front_matter = False
            for word in front_matter_words:
                if word in p.lower():
                    is_front_matter = True
                    break
            
            if not is_front_matter:
                return i
                
    return 0 # Safe fallback

def split_into_snippets(paragraphs: list[str], target_words: int = 280) -> list[str]:
    """
    Groups paragraphs into snippets of ~280 words, ensuring no mid-paragraph cuts.
    """
    snippets = []
    current_snippet = []
    current_word_count = 0
    
    for p in paragraphs:
        p_words = p.split()
        p_word_count = len(p_words)
        
        # If a single paragraph is extremely long, split it at sentence boundaries
        if p_word_count > (target_words * 1.5):
            # Split paragraph into sentences
            sentences = re.split(r'(?<=[.!?])\s+', p)
            temp_p = []
            temp_count = 0
            
            for s in sentences:
                s_count = len(s.split())
                if temp_count + s_count > target_words:
                    # Flush current group as a snippet if we already have something in current_snippet
                    if current_snippet:
                        snippets.append("\n\n".join(current_snippet))
                        current_snippet = []
                        current_word_count = 0
                    
                    # Also flush the current split paragraph if it reached target
                    if temp_p:
                        snippets.append(" ".join(temp_p))
                        temp_p = []
                        temp_count = 0
                
                temp_p.append(s)
                temp_count += s_count
            
            if temp_p:
                current_snippet.append(" ".join(temp_p))
                current_word_count += temp_count
            continue
            
        # Normal grouping logic
        if current_word_count + p_word_count > (target_words * 1.25) and current_word_count > (target_words * 0.75):
            snippets.append("\n\n".join(current_snippet))
            current_snippet = [p]
            current_word_count = p_word_count
        else:
            current_snippet.append(p)
            current_word_count += p_word_count
            
    if current_snippet:
        snippets.append("\n\n".join(current_snippet))
        
    return snippets

async def find_start_with_ai(snippets: list[str]) -> int:
    """
    Uses Gemini to identify the real start index of the book content.
    """
    if not snippets:
        return 0
        
    sample = snippets[:20]
    formatted_snippets = ""
    for i, s in enumerate(sample):
        formatted_snippets += f"--- SNIPPET {i} ---\n{s[:300]}...\n\n"
        
    prompt = f"""
    Here are the first 20 text snippets from a book, numbered 0-19.
    Some early snippets may be front matter (copyright, TOC, dedication, foreword).
    Reply with ONLY a single integer: the index of the first snippet that is actual readable book content.
    If all look fine, reply 0.

    {formatted_snippets}
    """
    
    try:
        response = await call_gemini(prompt, model_name="gemini-2.0-flash-lite", timeout=10.0)
        # Extract the first integer found in the response
        match = re.search(r'\d+', response)
        if match:
            idx = int(match.group())
            return min(idx, len(snippets) - 1)
    except Exception:
        pass
        
    return 0

def extract_pdf_raw(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()
    return full_text

def extract_epub_raw(file_bytes: bytes) -> str:
    book = epub.read_epub(io.BytesIO(file_bytes))
    full_text = ""
    for item in book.get_items():
        if item.get_type() == 9: # Document type
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            full_text += soup.get_text() + "\n"
    return full_text

async def process_pdf(file_bytes: bytes) -> dict:
    try:
        raw_text = extract_pdf_raw(file_bytes)
        cleaned_text = clean_text(raw_text)
        paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
        
        heuristics_start_p = find_content_start(paragraphs)
        # Shift paragraphs to start from heuristics
        relevant_paragraphs = paragraphs[heuristics_start_p:]
        
        snippets = split_into_snippets(relevant_paragraphs)
        if not snippets:
            return {"snippets": [], "suggested_start": 0}
            
        # Optional AI refinement
        ai_start = await find_start_with_ai(snippets)
        
        return {
            "snippets": snippets,
            "suggested_start": ai_start
        }
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return {"snippets": [], "suggested_start": 0}

async def process_epub(file_bytes: bytes) -> dict:
    try:
        raw_text = extract_epub_raw(file_bytes)
        cleaned_text = clean_text(raw_text)
        paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
        
        heuristics_start_p = find_content_start(paragraphs)
        relevant_paragraphs = paragraphs[heuristics_start_p:]
        
        snippets = split_into_snippets(relevant_paragraphs)
        if not snippets:
            return {"snippets": [], "suggested_start": 0}
            
        ai_start = await find_start_with_ai(snippets)
        
        return {
            "snippets": snippets,
            "suggested_start": ai_start
        }
    except Exception as e:
        print(f"Error processing EPUB: {e}")
        return {"snippets": [], "suggested_start": 0}

# Backward compatibility for existing router if needed
def extract_and_split(file_bytes: bytes, file_type: str = "pdf") -> list[str]:
    # This is a synchronous wrapper for the old API
    # Since the new logic is async (due to Gemini), we'll run it in a loop if needed,
    # but the router should probably be updated to call process_pdf/epub directly.
    loop = asyncio.get_event_loop()
    if file_type == "epub":
        res = loop.run_until_complete(process_epub(file_bytes))
    else:
        res = loop.run_until_complete(process_pdf(file_bytes))
    return res["snippets"]
