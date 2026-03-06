"""
SEO tracker — monitors meta tags, titles, headings, keyword density.
"""
import logging
from collections import Counter
import re

logger = logging.getLogger(__name__)

def analyze_seo(content, url):
    """Analyze SEO metrics from extracted content."""
    title = content.get("title", "")
    meta_desc = content.get("meta_description", "")
    headings = content.get("headings", [])
    full_text = content.get("full_text", "")
    ctas = content.get("ctas", [])
    
    # Title analysis
    title_length = len(title)
    title_score = 100 if 30 <= title_length <= 60 else 70 if 20 <= title_length <= 70 else 40
    
    # Meta description analysis
    meta_length = len(meta_desc)
    meta_score = 100 if 120 <= meta_length <= 160 else 70 if 80 <= meta_length <= 180 else 40 if meta_desc else 0
    
    # Headings analysis
    h1_count = sum(1 for h in headings if h.get("level") == "h1")
    h2_count = sum(1 for h in headings if h.get("level") == "h2")
    h3_count = sum(1 for h in headings if h.get("level") == "h3")
    heading_score = 100 if h1_count == 1 and h2_count >= 2 else 70 if h1_count >= 1 else 40
    
    # Content length
    word_count = len(full_text.split())
    content_score = 100 if word_count >= 1000 else 70 if word_count >= 500 else 40
    
    # Keyword extraction (top 10 words, excluding common)
    stop_words = {"the","a","an","and","or","but","in","on","at","to","for","of","with","by","from","is","are","was","were","be","been","being","have","has","had","do","does","did","will","would","could","should","may","might","shall","can","this","that","these","those","it","its","i","you","he","she","we","they","me","him","her","us","them","my","your","his","our","their","what","which","who","whom","when","where","why","how","all","each","every","both","few","more","most","other","some","such","no","not","only","own","same","so","than","too","very","just","about","up","out","if","then","also","as","into","over","after","before"}
    words = re.findall(r'[a-z]{3,}', full_text.lower())
    filtered = [w for w in words if w not in stop_words]
    top_keywords = Counter(filtered).most_common(10)
    
    # CTA count
    cta_score = 100 if len(ctas) >= 3 else 70 if len(ctas) >= 1 else 30
    
    # Overall score
    overall = int((title_score + meta_score + heading_score + content_score + cta_score) / 5)
    
    return {
        "url": url,
        "overall_score": overall,
        "title": {"text": title, "length": title_length, "score": title_score, "tip": "Ideal: 30-60 chars" if title_score < 100 else "Good"},
        "meta_description": {"text": meta_desc[:160], "length": meta_length, "score": meta_score, "tip": "Ideal: 120-160 chars" if meta_score < 100 else "Good"},
        "headings": {"h1": h1_count, "h2": h2_count, "h3": h3_count, "score": heading_score, "tip": "Need exactly 1 H1" if h1_count != 1 else "Good"},
        "content": {"word_count": word_count, "score": content_score, "tip": "Aim for 1000+ words" if content_score < 100 else "Good"},
        "ctas": {"count": len(ctas), "items": ctas[:5], "score": cta_score},
        "keywords": [{"word": w, "count": c} for w, c in top_keywords],
    }