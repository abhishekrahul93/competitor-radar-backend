"""
Slack API routes — test connection, save webhook, get status.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.slack_service import send_test_message

router = APIRouter(prefix="/slack", tags=["Slack"])


def get_user_id(user):
    """Get user ID whether user is a dict or object."""
    if isinstance(user, dict):
        return user.get("id") or user.get("user_id")
    return getattr(user, "id", None)


class WebhookRequest(BaseModel):
    webhook_url: str


class TestRequest(BaseModel):
    webhook_url: str


@router.post("/test")
async def test_slack_connection(req: TestRequest, user=Depends(get_current_user)):
    """Send a test message to verify Slack webhook URL works."""
    if not req.webhook_url or not req.webhook_url.startswith("https://hooks.slack.com/"):
        raise HTTPException(status_code=400, detail="Invalid Slack webhook URL. Must start with https://hooks.slack.com/")

    success = await send_test_message(req.webhook_url)
    if success:
        return {"status": "success", "message": "Test message sent! Check your Slack channel."}
    else:
        raise HTTPException(status_code=400, detail="Failed to send test message. Please check your webhook URL.")


@router.put("/webhook")
async def save_webhook(req: WebhookRequest, user=Depends(get_current_user), db=Depends(get_db)):
    """Save Slack webhook URL for the current user."""
    if req.webhook_url and not req.webhook_url.startswith("https://hooks.slack.com/"):
        raise HTTPException(status_code=400, detail="Invalid Slack webhook URL")

    uid = get_user_id(user)
    await db.execute(
        text("UPDATE users SET slack_webhook = :url WHERE id = :uid"),
        {"url": req.webhook_url, "uid": uid},
    )
    await db.commit()
    return {"status": "saved", "message": "Slack webhook saved successfully"}


@router.delete("/webhook")
async def remove_webhook(user=Depends(get_current_user), db=Depends(get_db)):
    """Remove Slack webhook URL for the current user."""
    uid = get_user_id(user)
    await db.execute(
        text("UPDATE users SET slack_webhook = '' WHERE id = :uid"),
        {"uid": uid},
    )
    await db.commit()
    return {"status": "removed", "message": "Slack integration disconnected"}


@router.get("/status")
async def get_slack_status(user=Depends(get_current_user), db=Depends(get_db)):
    """Check if Slack is configured for the current user."""
    uid = get_user_id(user)
    result = await db.execute(
        text("SELECT slack_webhook FROM users WHERE id = :uid"),
        {"uid": uid},
    )
    row = result.fetchone()
    webhook = row[0] if row and row[0] else ""

    return {
        "connected": bool(webhook),
        "webhook_url": webhook[:30] + "..." if webhook else "",
    }
