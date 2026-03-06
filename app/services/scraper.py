"""
Smart scraper — handles JS-protected sites with cloudscraper + fallback.
"""
import httpx
import cloudscraper
import hashlib
import json
import logging
import asyncio
import random
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
]

async def fetch_page(url, timeout=30):
    """Try httpx first, fall back to cloudscraper for JS-protected sites."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    # Try httpx first (async, fast)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            
            # Check if we got real content or a JS challenge
            if len(html) > 500 and "<body" in html.lower():
                soup = BeautifulSoup(html, "lxml")
                text = soup.get_text(strip=True)
                if len(text) > 100:
                    logger.info(f"httpx success: {url}")
                    return {"success": True, "html": html, "method": "httpx"}
            
            logger.info(f"httpx got thin content for {url}, trying cloudscraper")
    except Exception as e:
        logger.info(f"httpx failed for {url}: {e}, trying cloudscraper")
    
    # Fallback to cloudscraper (handles Cloudflare, JS challenges)
    try:
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        scraper.headers.update(headers)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: scraper.get(url, timeout=timeout))
        response.raise_for_status()
        html = response.text
        
        if len(html) > 200:
            logger.info(f"cloudscraper success: {url}")
            return {"success": True, "html": html, "method": "cloudscraper"}
    except Exception as e:
        logger.error(f"cloudscraper failed for {url}: {e}")
    
    # Final fallback — basic httpx without fancy headers
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url)
            return {"success": True, "html": response.text, "method": "basic"}
    except Exception as e:
        logger.error(f"All methods failed for {url}: {e}")
        return {"success": False, "html": "", "error": str(e)}


def extract_content(html, page_type):
    """Extract structured content from HTML."""
    soup = BeautifulSoup(html, "lxml")
    
    # Remove scripts and styles
    for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
        tag.decompose()
    
    content = {
        "title": "",
        "meta_description": "",
        "headings": [],
        "paragraphs": [],
        "links": [],
        "images": [],
        "full_text": "",
        "ctas": [],
    }
    
    # Title
    title_tag = soup.find("title")
    content["title"] = title_tag.get_text(strip=True) if title_tag else ""
    
    # Meta description
    meta = soup.find("meta", attrs={"name": "description"})
    content["meta_description"] = meta.get("content", "") if meta else ""
    
    # Headings
    for level in ["h1", "h2", "h3"]:
        for h in soup.find_all(level):
            text = h.get_text(strip=True)
            if text and len(text) > 2:
                content["headings"].append({"level": level, "text": text[:200]})
    
    # Paragraphs
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if text and len(text) > 20:
            content["paragraphs"].append(text[:500])
    
    # CTAs (buttons and links with action words)
    cta_words = ["sign up", "get started", "try free", "start", "buy", "subscribe", "demo", "pricing", "contact"]
    for tag in soup.find_all(["a", "button"]):
        text = tag.get_text(strip=True).lower()
        if any(w in text for w in cta_words):
            content["ctas"].append(tag.get_text(strip=True)[:100])
    
    # Page-type specific extraction
    if page_type == "pricing":
        content["pricing_data"] = extract_pricing(soup)
    elif page_type == "careers":
        content["jobs_data"] = extract_jobs(soup)
    
    # Full text
    content["full_text"] = soup.get_text(separator=" ", strip=True)[:10000]
    
    return content


def extract_pricing(soup):
    """Extract pricing information."""
    pricing = {"plans": [], "prices": [], "features": []}
    
    price_keywords = ["$", "€", "£", "/mo", "/month", "/year", "free", "starter", "pro", "enterprise", "business", "team"]
    
    for el in soup.find_all(["div", "section", "span", "p", "h2", "h3", "h4"]):
        text = el.get_text(strip=True)
        if any(k in text.lower() for k in price_keywords) and len(text) < 200:
            if "$" in text or "€" in text or "£" in text:
                pricing["prices"].append(text[:100])
            elif any(p in text.lower() for p in ["free", "starter", "pro", "enterprise", "business", "team", "basic"]):
                pricing["plans"].append(text[:100])
    
    return pricing


def extract_jobs(soup):
    """Extract job listings."""
    jobs = {"titles": [], "departments": [], "locations": []}
    
    job_keywords = ["engineer", "developer", "designer", "manager", "analyst", "scientist", "lead", "director", "head of", "vp of"]
    
    for el in soup.find_all(["h2", "h3", "h4", "a", "li", "div"]):
        text = el.get_text(strip=True)
        if any(k in text.lower() for k in job_keywords) and 5 < len(text) < 150:
            jobs["titles"].append(text[:100])
    
    dept_keywords = ["engineering", "product", "design", "marketing", "sales", "operations", "data", "research"]
    for el in soup.find_all(["h2", "h3", "span", "div"]):
        text = el.get_text(strip=True)
        if any(k in text.lower() for k in dept_keywords) and len(text) < 50:
            jobs["departments"].append(text[:50])
    
    return jobs


def compute_content_hash(content):
    """Create a hash of the content for change detection."""
    key_data = json.dumps({
        "title": content.get("title", ""),
        "headings": content.get("headings", []),
        "paragraphs": content.get("paragraphs", [])[:10],
        "ctas": content.get("ctas", []),
        "pricing_data": content.get("pricing_data", {}),
        "jobs_data": content.get("jobs_data", {}),
    }, sort_keys=True)
    return hashlib.sha256(key_data.encode()).hexdigest()