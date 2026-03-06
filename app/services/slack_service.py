"""
Slack notifications — sends change alerts to Slack channels.
"""
import httpx
import logging

logger = logging.getLogger(__name__)

async def send_slack_alert(webhook_url, competitor_name, page_type, changes, brief):
    if not webhook_url:
        return
    
    sig = max(c.get("significance", 0) for c in changes) if changes else 0
    emoji = "🔴" if sig >= 0.8 else "🟡" if sig >= 0.5 else "🟢"
    threat = brief.get("threat_level", "UNKNOWN")
    
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {competitor_name} — {page_type} changed"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Significance:* {int(sig*100)}% | *Threat:* {threat}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*What Changed*\n{brief.get('what_changed', 'See dashboard')}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Why It Matters*\n{brief.get('why_it_matters', '')}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*What To Do*\n{brief.get('what_to_do', '')}"}},
        {"type": "divider"},
        {"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "View Dashboard"}, "url": "https://competitor-radar-frontend.vercel.app", "style": "primary"}]}
    ]
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json={"blocks": blocks, "text": f"{competitor_name} changed their {page_type}"})
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {competitor_name}/{page_type}")
            else:
                logger.error(f"Slack error: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Slack failed: {e}")


async def send_slack_weekly(webhook_url, changes_by_competitor, total_changes, total_briefs):
    if not webhook_url:
        return
    
    comp_lines = ""
    for name, data in changes_by_competitor.items():
        emoji = "🔴" if data["max_significance"] >= 0.8 else "🟡" if data["max_significance"] >= 0.5 else "🟢"
        comp_lines += f"{emoji} *{name}*: {data['count']} changes — {data['top_change'][:80]}\n"
    
    high = sum(1 for d in changes_by_competitor.values() if d["max_significance"] >= 0.8)
    
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📊 Weekly Intelligence Digest"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{total_changes}* changes | *{high}* high priority | *{total_briefs}* AI briefs | *{len(changes_by_competitor)}* competitors"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": comp_lines or "No changes this week."}},
        {"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "View Full Report"}, "url": "https://competitor-radar-frontend.vercel.app", "style": "primary"}]}
    ]
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"blocks": blocks, "text": f"Weekly digest: {total_changes} changes detected"})
            logger.info("Slack weekly digest sent")
    except Exception as e:
        logger.error(f"Slack weekly failed: {e}")