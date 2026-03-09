"""
Slack integration service — sends competitive intelligence alerts to Slack.
Color-coded by change type, includes AI brief inline.
"""
import logging
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

# Color codes by change category
COLORS = {
    "pricing": "#ef4444",     # red — highest urgency
    "hiring": "#f59e0b",      # amber
    "messaging": "#06b6d4",   # cyan
    "content": "#10b981",     # green
    "conversion": "#6366f1",  # indigo
    "seo": "#8b5cf6",         # purple
    "other": "#64748b",       # gray
}

SIGNIFICANCE_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}


def _get_significance_label(score: float) -> str:
    if score >= 0.9:
        return "critical"
    elif score >= 0.7:
        return "high"
    elif score >= 0.5:
        return "medium"
    return "low"


async def send_slack_alert(
    webhook_url: str,
    competitor_name: str,
    change_summary: str,
    change_category: str = "other",
    significance: float = 0.5,
    page_type: str = "",
    ai_brief: dict = None,
    dashboard_url: str = "https://competitor-radar-frontend.vercel.app",
) -> bool:
    """
    Send a competitive intelligence alert to Slack.
    Returns True if successful, False otherwise.
    """
    if not webhook_url:
        logger.warning("No Slack webhook URL configured")
        return False

    sig_label = _get_significance_label(significance)
    sig_emoji = SIGNIFICANCE_EMOJI.get(sig_label, "⚪")
    color = COLORS.get(change_category, COLORS["other"])
    sig_pct = f"{int(significance * 100)}%"
    timestamp = datetime.now().strftime("%b %d, %Y at %I:%M %p")

    # Build the main alert block
    fields = [
        {"title": "Competitor", "value": competitor_name, "short": True},
        {"title": "Change Type", "value": change_category.title(), "short": True},
        {"title": "Significance", "value": f"{sig_emoji} {sig_pct} ({sig_label.upper()})", "short": True},
        {"title": "Page", "value": page_type.title() if page_type else "N/A", "short": True},
    ]

    # Add AI brief sections if available
    brief_text = ""
    if ai_brief:
        if ai_brief.get("what_changed"):
            brief_text += f"*What Changed:*\n{ai_brief['what_changed']}\n\n"
        if ai_brief.get("why_it_matters"):
            brief_text += f"*Why It Matters:*\n{ai_brief['why_it_matters']}\n\n"
        if ai_brief.get("what_to_do"):
            brief_text += f"*What To Do:*\n{ai_brief['what_to_do']}\n\n"
        if ai_brief.get("threat_level"):
            brief_text += f"*Threat Level:* {ai_brief['threat_level']}"

    payload = {
        "text": f"{sig_emoji} CompetitorRadar: {competitor_name} — {change_summary}",
        "attachments": [
            {
                "color": color,
                "pretext": f"{sig_emoji} *Competitor Change Detected*",
                "title": change_summary,
                "fields": fields,
                "text": brief_text if brief_text else "_No AI brief available. Add an API key in Settings for AI analysis._",
                "footer": f"CompetitorRadar | {timestamp}",
                "footer_icon": "https://comp-radar.com/favicon.ico",
                "actions": [
                    {
                        "type": "button",
                        "text": "View Dashboard",
                        "url": dashboard_url,
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": f"View {competitor_name}",
                        "url": f"{dashboard_url}?competitor={competitor_name}",
                    },
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {competitor_name} — {change_category}")
                return True
            else:
                logger.error(f"Slack webhook failed ({response.status_code}): {response.text}")
                return False
    except Exception as e:
        logger.error(f"Slack alert error: {e}")
        return False


async def send_test_message(webhook_url: str) -> bool:
    """Send a test message to verify Slack webhook works."""
    if not webhook_url:
        return False

    payload = {
        "text": "✅ *CompetitorRadar Connected!*",
        "attachments": [
            {
                "color": "#10b981",
                "text": "Your Slack integration is working. You'll receive alerts here when competitor changes are detected.\n\n"
                        "• 🔴 *Pricing changes* — highest priority\n"
                        "• 🟠 *Hiring signals* — new roles & departments\n"
                        "• 🟡 *Messaging shifts* — headline & CTA changes\n"
                        "• 🟢 *Content updates* — docs, blog, SEO changes",
                "footer": f"CompetitorRadar | Test message | {datetime.now().strftime('%b %d, %Y at %I:%M %p')}",
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Slack test failed: {e}")
        return False


async def send_weekly_digest(webhook_url: str, summary: dict) -> bool:
    """Send weekly digest summary to Slack."""
    if not webhook_url:
        return False

    total = summary.get("total_changes", 0)
    critical = summary.get("critical", 0)
    competitors = summary.get("competitors_active", 0)

    payload = {
        "text": f"📊 *Weekly CompetitorRadar Digest* — {total} changes detected",
        "attachments": [
            {
                "color": "#6366f1",
                "fields": [
                    {"title": "Total Changes", "value": str(total), "short": True},
                    {"title": "Critical Alerts", "value": f"🔴 {critical}", "short": True},
                    {"title": "Active Competitors", "value": str(competitors), "short": True},
                ],
                "text": summary.get("ai_summary", ""),
                "footer": f"CompetitorRadar Weekly Digest | {datetime.now().strftime('%b %d, %Y')}",
                "actions": [
                    {
                        "type": "button",
                        "text": "View Full Report",
                        "url": "https://competitor-radar-frontend.vercel.app",
                        "style": "primary",
                    }
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Slack weekly digest error: {e}")
        return False
