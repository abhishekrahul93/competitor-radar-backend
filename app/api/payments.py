"""
Stripe payment endpoints — checkout sessions and plan management.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.models import User
import stripe
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY

PLANS = {
    "pro": {
        "name": "Pro",
        "price": 2900,
        "currency": "usd",
        "interval": "month",
        "features": ["25 competitors", "Auto-scan every 12h", "AI strategic briefs", "Email alerts"],
    },
    "team": {
        "name": "Team",
        "price": 7900,
        "currency": "usd",
        "interval": "month",
        "features": ["Unlimited competitors", "Auto-scan every 6h", "Weekly reports", "Slack integration", "API access"],
    },
}

class CheckoutRequest(BaseModel):
    plan: str

@router.get("/plans")
async def get_plans():
    return PLANS

@router.get("/config")
async def get_config():
    return {"publishable_key": settings.STRIPE_PUBLISHABLE_KEY}

@router.post("/create-checkout")
async def create_checkout(
    req: CheckoutRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if req.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = PLANS[req.plan]
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": plan["currency"],
                    "product_data": {"name": f"CompetitorRadar {plan['name']} Plan"},
                    "unit_amount": plan["price"],
                    "recurring": {"interval": plan["interval"]},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url="https://competitor-radar-frontend.vercel.app/?payment=success",
            cancel_url="https://competitor-radar-frontend.vercel.app/?payment=cancelled",
            client_reference_id=str(current_user["user_id"]),
            metadata={"plan": req.plan, "user_id": str(current_user["user_id"])},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    try:
        if settings.STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        else:
            event = stripe.Event.construct_from(stripe.util.json.loads(payload), stripe.api_key)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        plan = session.get("metadata", {}).get("plan", "pro")
        
        if user_id:
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalar_one_or_none()
            if user:
                user.plan = plan
                await db.commit()
                logger.info(f"User {user_id} upgraded to {plan}")
    
    elif event["type"] == "customer.subscription.deleted":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        if user_id:
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalar_one_or_none()
            if user:
                user.plan = "free"
                await db.commit()
                logger.info(f"User {user_id} downgraded to free")
    
    return {"status": "ok"}

@router.get("/status")
async def payment_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    return {"plan": user.plan if user else "free"}