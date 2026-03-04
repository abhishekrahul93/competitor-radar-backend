"""
AI Strategic Analyst — generates intelligence briefs from detected changes.
"""
import json
import logging
import httpx
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

BRIEF_PROMPT = """You are an elite competitive intelligence analyst advising a startup founder.

COMPETITOR: {competitor}
PAGE: {page_type}
DATE: {date}

CHANGES DETECTED:
{changes}

Write a strategic intelligence brief. Use EXACTLY this format with these 4 headers:

## WHAT CHANGED
2-3 sentences describing exactly what changed. Be specific.

## WHY IT MATTERS
3-4 sentences on strategic significance. Is this a threat or opportunity? What does it signal about their direction?

## WHAT YOU SHOULD DO
3 specific, actionable recommendations. Not generic advice — concrete steps.

## THREAT LEVEL
One of: CRITICAL / HIGH / MEDIUM / LOW
One sentence justification.

Keep under 300 words total. Be direct. No filler."""

WEEKLY_PROMPT = """You are an elite competitive intelligence analyst.

Write a weekly intelligence brief based on all competitor changes this week.

CHANGES THIS WEEK:
{changes}

Format:

## EXECUTIVE SUMMARY
3-4 sentences on the most important competitive movements.

## TOP THREATS
2-3 most significant threats with specifics.

## OPPORTUNITIES
What gaps or weaknesses have competitors revealed?

## MARKET SIGNALS
Patterns across competitors. Where is the market heading?

## THIS WEEK'S ACTIONS
3-5 specific things the founder should do this week.

Keep under 500 words. Be strategic and direct."""


async def generate_brief(competitor_name: str, page_type: str, changes: list) -> dict:
    """Generate AI strategic brief for detected changes."""
    changes_text = "\n".join(
        f"- [{c.get('category', 'unknown').upper()}] {c.get('summary', '')} (significance: {c.get('significance', 0):.0%})"
        for c in changes
    )
    
    prompt = BRIEF_PROMPT.format(
        competitor=competitor_name,
        page_type=page_type,
        date=datetime.now().strftime("%B %d, %Y"),
        changes=changes_text,
    )
    
    response_text = await _call_llm(prompt)
    
    if not response_text:
        return _demo_brief(competitor_name, changes)
    
    # Parse sections
    brief = _parse_brief(response_text)
    brief["full_analysis"] = response_text
    return brief


async def generate_weekly_report(changes_by_competitor: dict) -> dict:
    """Generate weekly intelligence report."""
    changes_text = ""
    for comp, changes in changes_by_competitor.items():
        changes_text += f"\n### {comp}\n"
        for c in changes:
            changes_text += f"- [{c.get('page_type', '')}] {c.get('summary', '')} (significance: {c.get('significance', 0):.0%})\n"
    
    prompt = WEEKLY_PROMPT.format(changes=changes_text)
    response_text = await _call_llm(prompt)
    
    return {"full_analysis": response_text or "Weekly report generation requires an API key."}


async def _call_llm(prompt: str) -> str:
    """Call OpenAI or Anthropic API."""
    if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return await _call_openai(prompt)
    elif settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        return await _call_anthropic(prompt)
    return ""


async def _call_openai(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a competitive intelligence analyst. Be concise and strategic."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return ""


async def _call_anthropic(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            data = response.json()
            return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return ""


def _parse_brief(text: str) -> dict:
    """Parse AI response into structured sections."""
    sections = {"what_changed": "", "why_it_matters": "", "what_to_do": "", "threat_level": ""}
    
    current = None
    lines = text.split("\n")
    
    for line in lines:
        lower = line.lower().strip()
        if "what changed" in lower:
            current = "what_changed"
        elif "why it matters" in lower:
            current = "why_it_matters"
        elif "what you should do" in lower or "what to do" in lower:
            current = "what_to_do"
        elif "threat level" in lower:
            current = "threat_level"
        elif current and line.strip():
            sections[current] += line.strip() + "\n"
    
    for key in sections:
        sections[key] = sections[key].strip()
    
    return sections


def _demo_brief(competitor_name: str, changes: list) -> dict:
    top_change = changes[0] if changes else {}
    return {
        "what_changed": f"Changes detected on {competitor_name}: {top_change.get('summary', 'Multiple updates found')}",
        "why_it_matters": "Connect your OpenAI or Anthropic API key in settings to get AI-powered strategic analysis of every competitor change.",
        "what_to_do": "1. Add your API key in the Settings page\n2. Re-run the scan to generate full AI briefs\n3. Review briefs weekly for strategic insights",
        "threat_level": "UNKNOWN — API key required for threat assessment",
        "full_analysis": "Demo mode. Add an API key for full AI analysis.",
    }
