"""
Production web scraper — fetches and extracts structured content from competitor pages.
"""
import httpx
from bs4 import BeautifulSoup
import hashlib
import re
import asyncio
import random
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch_page(url: str, timeout: int = 30) -> dict:
    """Fetch a page with async HTTP client."""
    try:
        await asyncio.sleep(random.uniform(1.0, 2.5))
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status()
            return {"success": True, "html": response.text, "status": response.status_code, "url": str(response.url)}
    except Exception as e:
        logger.error(f"Fetch failed for {url}: {e}")
        return {"success": False, "error": str(e), "url": url}


def extract_content(html: str, page_type: str = "homepage") -> dict:
    """Extract structured content based on page type."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript", "header"]):
        tag.decompose()
    
    extractors = {
        "homepage": _extract_homepage,
        "pricing": _extract_pricing,
        "careers": _extract_careers,
        "docs": _extract_general,
    }
    
    extractor = extractors.get(page_type, _extract_general)
    data = extractor(soup)
    data["page_type"] = page_type
    return data


def _extract_homepage(soup):
    title = soup.find("title")
    meta = soup.find("meta", attrs={"name": "description"})
    
    headings = []
    for level in ["h1", "h2", "h3"]:
        for h in soup.find_all(level):
            text = h.get_text(strip=True)
            if text and 3 < len(text) < 300:
                headings.append({"level": level, "text": text})
    
    messages = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if 30 < len(text) < 500:
            messages.append(text)
    
    ctas = []
    for btn in soup.find_all(["button", "a"]):
        text = btn.get_text(strip=True)
        if text and len(text) < 50:
            keywords = ["start", "try", "sign up", "get started", "demo", "free", "pricing", "buy", "subscribe"]
            if any(k in text.lower() for k in keywords):
                ctas.append(text)
    
    full_text = soup.get_text(separator="\n", strip=True)[:10000]
    
    return {
        "title": title.get_text(strip=True) if title else "",
        "meta_description": meta.get("content", "") if meta else "",
        "headings": headings,
        "key_messages": messages[:20],
        "cta_buttons": list(set(ctas)),
        "full_text": full_text,
    }


def _extract_pricing(soup):
    title = soup.find("title")
    
    # Find prices
    price_pattern = re.compile(r'\$\d[\d,]*\.?\d*(?:\s*/\s*\w+)?')
    prices = []
    for el in soup.find_all(string=price_pattern):
        found = price_pattern.findall(el)
        prices.extend(found)
    prices = list(set(prices))
    
    # Plan names
    plans = []
    for h in soup.find_all(["h2", "h3", "h4"]):
        text = h.get_text(strip=True)
        if text and len(text) < 60:
            plans.append(text)
    
    # Features
    features = []
    for ul in soup.find_all("ul"):
        items = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True) and len(li.get_text(strip=True)) < 200]
        if 2 <= len(items) <= 30:
            features.append(items)
    
    full_text = soup.get_text(separator="\n", strip=True)[:10000]
    
    return {
        "title": title.get_text(strip=True) if title else "",
        "prices": prices,
        "plans": plans,
        "features": features,
        "full_text": full_text,
    }


def _extract_careers(soup):
    title = soup.find("title")
    
    job_keywords = ["engineer", "developer", "designer", "manager", "analyst", "scientist",
                    "lead", "director", "head of", "vp ", "architect", "specialist", "coordinator"]
    
    jobs = []
    seen = set()
    for el in soup.find_all(["h2", "h3", "h4", "a", "li", "div"]):
        text = el.get_text(strip=True)
        if text and 10 < len(text) < 150 and text not in seen:
            if any(k in text.lower() for k in job_keywords):
                href = el.get("href", "")
                jobs.append({"title": text, "url": href})
                seen.add(text)
    
    departments = set()
    dept_keywords = ["engineering", "product", "design", "marketing", "sales", "operations",
                     "data", "machine learning", "ai", "research", "finance", "legal", "people"]
    for el in soup.find_all(["h2", "h3", "span"]):
        text = el.get_text(strip=True).lower()
        for d in dept_keywords:
            if d in text and len(text) < 50:
                departments.add(text)
    
    full_text = soup.get_text(separator="\n", strip=True)[:10000]
    
    return {
        "title": title.get_text(strip=True) if title else "",
        "job_listings": jobs,
        "departments": list(departments),
        "job_count": len(jobs),
        "full_text": full_text,
    }


def _extract_general(soup):
    title = soup.find("title")
    headings = []
    for level in ["h1", "h2", "h3"]:
        for h in soup.find_all(level):
            text = h.get_text(strip=True)
            if text and len(text) < 300:
                headings.append({"level": level, "text": text})
    
    full_text = soup.get_text(separator="\n", strip=True)[:10000]
    
    return {
        "title": title.get_text(strip=True) if title else "",
        "headings": headings,
        "full_text": full_text,
    }


def compute_content_hash(content: dict) -> str:
    """Hash meaningful content for change detection."""
    parts = [
        str(content.get("title", "")),
        str(content.get("headings", "")),
        str(content.get("prices", "")),
        str(content.get("plans", "")),
        str(content.get("job_listings", "")),
        str(content.get("cta_buttons", "")),
        str(content.get("meta_description", "")),
    ]
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()
