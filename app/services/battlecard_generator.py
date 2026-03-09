"""
AI Battlecard Generator — creates one-page competitive battlecards.
Sales teams use these during calls to counter competitor objections.
"""
import logging
import httpx
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

BATTLECARD_PROMPT = """You are an elite competitive intelligence analyst creating a sales battlecard.

YOUR PRODUCT: CompetitorRadar (AI-powered competitive intelligence, $29/mo)
COMPETITOR: {competitor_name}
COMPETITOR URL: {competitor_url}

RECENT CHANGES DETECTED:
{recent_changes}

AI BRIEFS ON THIS COMPETITOR:
{ai_briefs}

Generate a sales battlecard in EXACTLY this JSON format (no markdown, no code fences, just raw JSON):
{{
  "competitor_overview": "2-3 sentence summary of who they are and what they do",
  "their_strengths": ["strength 1", "strength 2", "strength 3"],
  "their_weaknesses": ["weakness 1", "weakness 2", "weakness 3"],
  "our_advantages": ["advantage 1", "advantage 2", "advantage 3"],
  "pricing_comparison": "Brief comparison of their pricing vs ours",
  "key_differentiators": "2-3 sentences on what makes us fundamentally different",
  "objection_handlers": [
    {{"objection": "Customer says X", "response": "You should say Y"}},
    {{"objection": "Customer says X", "response": "You should say Y"}},
    {{"objection": "Customer says X", "response": "You should say Y"}}
  ],
  "win_themes": ["Theme 1 - when to use this angle", "Theme 2", "Theme 3"],
  "landmines": ["Question to ask prospect that exposes competitor weakness 1", "Question 2"],
  "quick_pitch": "30-second elevator pitch positioning against this competitor",
  "threat_level": "CRITICAL / HIGH / MEDIUM / LOW",
  "last_signal": "Most recent competitive signal detected"
}}

Be specific and actionable. Sales reps will use this on live calls."""


async def generate_battlecard(competitor: dict, changes: list, briefs: list) -> dict:
    """Generate an AI battlecard for a competitor."""
    changes_text = "\n".join(
        f"- [{c.get('change_category', 'unknown')}] {c.get('summary', '')} (significance: {c.get('significance', 0):.0%})"
        for c in changes[:10]
    ) or "No recent changes detected."

    briefs_text = "\n".join(
        f"- {b.get('title', '')}: {b.get('what_changed', '')[:100]}"
        for b in briefs[:5]
    ) or "No AI briefs available."

    prompt = BATTLECARD_PROMPT.format(
        competitor_name=competitor.get("name", "Unknown"),
        competitor_url=competitor.get("website_url", ""),
        recent_changes=changes_text,
        ai_briefs=briefs_text,
    )

    response_text = await _call_llm(prompt)

    if not response_text:
        return _demo_battlecard(competitor, changes)

    # Parse JSON response
    import json
    try:
        # Clean up response — remove code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        battlecard = json.loads(cleaned)
        battlecard["competitor_name"] = competitor.get("name", "Unknown")
        battlecard["competitor_url"] = competitor.get("website_url", "")
        battlecard["generated_at"] = datetime.now().isoformat()
        battlecard["source"] = "ai"
        return battlecard
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse battlecard JSON: {e}")
        return _demo_battlecard(competitor, changes)


async def _call_llm(prompt: str) -> str:
    """Call OpenAI or Anthropic API."""
    if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                    json={"model": settings.AI_MODEL, "messages": [
                        {"role": "system", "content": "You are a competitive intelligence analyst. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ], "max_tokens": 2000, "temperature": 0.3},
                )
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return ""
    elif settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": settings.ANTHROPIC_API_KEY, "Content-Type": "application/json", "anthropic-version": "2023-06-01"},
                    json={"model": "claude-sonnet-4-20250514", "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]},
                )
                return response.json()["content"][0]["text"]
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return ""
    return ""


def _demo_battlecard(competitor: dict, changes: list) -> dict:
    """Fallback battlecard when no API key is configured."""
    name = competitor.get("name", "Competitor")
    top_change = changes[0].get("summary", "No changes detected") if changes else "No changes detected"
    return {
        "competitor_name": name,
        "competitor_url": competitor.get("website_url", ""),
        "competitor_overview": f"{name} is a competitor in your space. Add your OpenAI or Anthropic API key to generate a full AI-powered battlecard.",
        "their_strengths": ["Established brand presence", "Existing customer base", "Feature depth in core product"],
        "their_weaknesses": ["Higher pricing", "Complex onboarding", "Slow to innovate"],
        "our_advantages": ["AI-powered strategic briefs", "10x more affordable", "Automated scanning every 12h"],
        "pricing_comparison": f"Add an API key to get detailed pricing comparison with {name}.",
        "key_differentiators": "CompetitorRadar provides AI-written strategic briefs, not just alerts. Every change is analyzed for significance and actionable recommendations.",
        "objection_handlers": [
            {"objection": f"We already use {name}", "response": "How often do you actually check it? CompetitorRadar sends you briefs automatically — you wake up to insights."},
            {"objection": "Your product is newer", "response": "That means we're built on the latest AI — GPT-4 writes your briefs, not templates from 2019."},
            {"objection": "We need enterprise features", "response": "We have team collaboration, Slack alerts, and API access on our Team plan at $79/mo."},
        ],
        "win_themes": ["Automation over manual checking", "AI analysis vs raw data", "Startup-friendly pricing"],
        "landmines": [f"Ask: 'How quickly did you find out about {name}'s last pricing change?'", "Ask: 'How many hours per week does your team spend manually checking competitors?'"],
        "quick_pitch": f"CompetitorRadar gives you what {name} charges thousands for — AI-powered competitive intelligence — at a fraction of the cost, fully automated.",
        "threat_level": "MEDIUM",
        "last_signal": top_change,
        "generated_at": datetime.now().isoformat(),
        "source": "demo",
    }
