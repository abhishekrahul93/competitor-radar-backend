"""
Change detection engine — compares snapshots to find meaningful differences.
"""
import difflib
import json
from typing import Optional, List

SIGNIFICANCE_SCORES = {
    "pricing_change": 0.95, "plan_added": 0.90, "plan_removed": 0.88,
    "jobs_added": 0.78, "new_departments": 0.80, "jobs_removed": 0.40,
    "title_change": 0.72, "cta_change": 0.68, "headings_added": 0.62,
    "headings_removed": 0.58, "meta_change": 0.52,
    "content_added": 0.48, "content_removed": 0.42,
}

def detect_changes(old: dict, new: dict, page_type: str) -> Optional[List[dict]]:
    if not old or not new:
        return None
    
    changes = []
    
    if page_type == "homepage":
        changes.extend(_homepage_changes(old, new))
    elif page_type == "pricing":
        changes.extend(_pricing_changes(old, new))
    elif page_type == "careers":
        changes.extend(_careers_changes(old, new))
    
    changes.extend(_text_changes(old.get("full_text", ""), new.get("full_text", "")))
    
    if not changes:
        return None
    
    for c in changes:
        c["significance"] = SIGNIFICANCE_SCORES.get(c["type"], 0.30)
        if page_type == "pricing":
            c["significance"] = min(c["significance"] * 1.15, 1.0)
    
    changes.sort(key=lambda x: x["significance"], reverse=True)
    return changes


def _homepage_changes(old, new):
    changes = []
    
    if old.get("title") != new.get("title") and new.get("title"):
        changes.append({
            "type": "title_change", "category": "messaging",
            "old": old["title"], "new": new["title"],
            "summary": f"Title changed: '{old.get('title', '')}' → '{new.get('title', '')}'"
        })
    
    old_h = set(h["text"] for h in old.get("headings", []))
    new_h = set(h["text"] for h in new.get("headings", []))
    added = new_h - old_h
    removed = old_h - new_h
    
    if added:
        changes.append({
            "type": "headings_added", "category": "messaging",
            "new": list(added)[:5],
            "summary": f"New headings: {', '.join(list(added)[:3])}"
        })
    if removed:
        changes.append({
            "type": "headings_removed", "category": "messaging",
            "old": list(removed)[:5],
            "summary": f"Removed headings: {', '.join(list(removed)[:3])}"
        })
    
    old_cta = set(old.get("cta_buttons", []))
    new_cta = set(new.get("cta_buttons", []))
    if old_cta != new_cta:
        changes.append({
            "type": "cta_change", "category": "conversion",
            "old": list(old_cta), "new": list(new_cta),
            "summary": f"CTAs changed: {', '.join(new_cta)}"
        })
    
    if old.get("meta_description") != new.get("meta_description") and new.get("meta_description"):
        changes.append({
            "type": "meta_change", "category": "seo",
            "old": old.get("meta_description", ""), "new": new["meta_description"],
            "summary": "Meta description updated (SEO strategy change)"
        })
    
    return changes


def _pricing_changes(old, new):
    changes = []
    
    old_p = set(old.get("prices", []))
    new_p = set(new.get("prices", []))
    if old_p != new_p:
        changes.append({
            "type": "pricing_change", "category": "pricing",
            "old": list(old_p), "new": list(new_p),
            "added": list(new_p - old_p), "removed": list(old_p - new_p),
            "summary": f"Prices changed: {', '.join(new_p)} (was: {', '.join(old_p)})"
        })
    
    old_plans = set(old.get("plans", []))
    new_plans = set(new.get("plans", []))
    added = new_plans - old_plans
    removed = old_plans - new_plans
    
    if added:
        changes.append({
            "type": "plan_added", "category": "pricing",
            "new": list(added),
            "summary": f"New plans: {', '.join(added)}"
        })
    if removed:
        changes.append({
            "type": "plan_removed", "category": "pricing",
            "old": list(removed),
            "summary": f"Plans removed: {', '.join(removed)}"
        })
    
    return changes


def _careers_changes(old, new):
    changes = []
    
    old_jobs = set(j["title"] for j in old.get("job_listings", []))
    new_jobs = set(j["title"] for j in new.get("job_listings", []))
    added = new_jobs - old_jobs
    removed = old_jobs - new_jobs
    
    if added:
        changes.append({
            "type": "jobs_added", "category": "hiring",
            "new": list(added)[:10],
            "summary": f"New jobs posted: {', '.join(list(added)[:3])}"
        })
    if removed:
        changes.append({
            "type": "jobs_removed", "category": "hiring",
            "old": list(removed)[:10],
            "summary": f"Jobs removed (filled?): {', '.join(list(removed)[:3])}"
        })
    
    old_d = set(old.get("departments", []))
    new_d = set(new.get("departments", []))
    if new_d - old_d:
        changes.append({
            "type": "new_departments", "category": "hiring",
            "new": list(new_d - old_d),
            "summary": f"New departments hiring: {', '.join(new_d - old_d)}"
        })
    
    return changes


def _text_changes(old_text, new_text):
    if not old_text or not new_text:
        return []
    
    sim = difflib.SequenceMatcher(None, old_text[:5000], new_text[:5000]).ratio()
    if sim >= 0.92:
        return []
    
    old_lines = old_text.split("\n")[:100]
    new_lines = new_text.split("\n")[:100]
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++") and len(l.strip()) > 15]
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---") and len(l.strip()) > 15]
    
    changes = []
    if added:
        changes.append({
            "type": "content_added", "category": "content",
            "new": added[:15], "similarity": round(sim, 3),
            "summary": f"Content added ({len(added)} sections, {sim:.0%} similarity)"
        })
    if removed:
        changes.append({
            "type": "content_removed", "category": "content",
            "old": removed[:15], "similarity": round(sim, 3),
            "summary": f"Content removed ({len(removed)} sections)"
        })
    
    return changes
