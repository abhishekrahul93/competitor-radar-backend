"""
Demo data endpoint with error logging.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Competitor, Change, Report
import logging
import traceback

logger = logging.getLogger(__name__)
router = APIRouter()

DEMO_DATA = [
    {
        "name": "Jasper AI",
        "website_url": "https://jasper.ai",
        "pricing_url": "https://jasper.ai/pricing",
        "careers_url": "https://jasper.ai/careers",
        "category": "AI SaaS",
        "changes": [
            {
                "page_type": "pricing",
                "change_type": "pricing_change",
                "change_category": "pricing",
                "summary": "Pro plan price increased from $39/mo to $49/mo. New Business plan added at $69/mo.",
                "significance": 0.95,
                "title": "Jasper AI - pricing changes detected",
                "what_changed": "Jasper raised their Pro plan from $39/month to $49/month. They also launched a new Business plan at $69/month with team features and API access.",
                "why_it_matters": "This signals Jasper is moving upmarket. The price increase will push budget-conscious users to seek alternatives. The new Business tier targets mid-market teams.",
                "what_to_do": "1. Maintain your current pricing to capture unhappy Jasper users.\n2. Create comparison content targeting Jasper alternative keywords.\n3. Monitor Jasper reviews on G2 for the next 30 days.",
                "threat_level": "HIGH - Pricing creates immediate acquisition opportunity",
            },
            {
                "page_type": "careers",
                "change_type": "jobs_added",
                "change_category": "hiring",
                "summary": "4 new ML Engineer positions posted focused on multimodal AI and computer vision.",
                "significance": 0.82,
                "title": "Jasper AI - careers changes detected",
                "what_changed": "Jasper posted 4 new roles: 2 Senior ML Engineers, 1 Computer Vision Lead, 1 Research Scientist. All SF-based, $200-350K salary range.",
                "why_it_matters": "Jasper is building in-house multimodal capabilities. The Computer Vision hire means they are building proprietary models. This could create a significant product moat.",
                "what_to_do": "1. Evaluate your own multimodal roadmap.\n2. Partner with an existing image AI provider to ship faster.\n3. Track their GitHub activity for early signals.",
                "threat_level": "HIGH - Signals product expansion that redefines landscape",
            }
        ]
    },
    {
        "name": "Copy.ai",
        "website_url": "https://copy.ai",
        "pricing_url": "https://copy.ai/pricing",
        "category": "AI SaaS",
        "changes": [
            {
                "page_type": "homepage",
                "change_type": "title_change",
                "change_category": "messaging",
                "summary": "Homepage repositioned from AI Content Platform to AI Sales Agent That Closes Deals.",
                "significance": 0.72,
                "title": "Copy.ai - homepage changes detected",
                "what_changed": "Copy.ai changed their headline from AI-Powered Content Platform to The AI Sales Agent That Closes Deals. They added sales workflow sections and CRM integrations.",
                "why_it_matters": "Copy.ai is pivoting from content generation to sales automation. They are exiting the crowded AI writing space for AI sales tech with higher willingness-to-pay.",
                "what_to_do": "1. Copy.ai is becoming less of a direct competitor. Sharpen your content positioning.\n2. Their content customers will churn - create targeted campaigns.\n3. Evaluate whether sales features could expand your market.",
                "threat_level": "MEDIUM - Reduces direct competition but signals market shift",
            }
        ]
    },
    {
        "name": "Writesonic",
        "website_url": "https://writesonic.com",
        "pricing_url": "https://writesonic.com/pricing",
        "category": "AI SaaS",
        "changes": [
            {
                "page_type": "pricing",
                "change_type": "pricing_change",
                "change_category": "pricing",
                "summary": "Pro plan price increased from $19/mo to $29/mo. Free tier reduced from 10K to 2.5K words.",
                "significance": 0.95,
                "title": "Writesonic - pricing changes detected",
                "what_changed": "Writesonic raised Pro from $19/month to $29/month - a 53% price hike. Free tier cut from 10,000 to 2,500 words/month.",
                "why_it_matters": "Writesonic is moving upmarket. The free tier cut forces users into paid plans. Any competitor at the old $19 price point now has a major acquisition advantage.",
                "what_to_do": "1. Maintain your pricing to capture unhappy Writesonic users.\n2. Monitor reviews on G2 and Twitter for 30 days.\n3. Target Writesonic alternative in SEO - traffic will spike.",
                "threat_level": "HIGH - Pricing creates immediate acquisition opportunity",
            },
            {
                "page_type": "homepage",
                "change_type": "headings_added",
                "change_category": "messaging",
                "summary": "New Enterprise tier added with SOC 2 Type II compliance badge prominently displayed.",
                "significance": 0.72,
                "title": "Writesonic - homepage changes detected",
                "what_changed": "Writesonic launched an Enterprise tier with custom pricing, SSO, dedicated support, and SLA guarantees. SOC 2 Type II badge now on homepage.",
                "why_it_matters": "Writesonic is targeting enterprise. SOC 2 compliance takes 6+ months - this shows serious commitment. They are leaving the SMB space.",
                "what_to_do": "1. If enterprise is not your target, celebrate - they are leaving SMB.\n2. If you target enterprise, SOC 2 is becoming table stakes.\n3. Marketing angle: Built for creators, not committees.",
                "threat_level": "MEDIUM - Enterprise shift reduces SMB competition",
            }
        ]
    }
]

@router.post("/setup")
async def setup_demo(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        user_id = current_user["user_id"]
        logger.info(f"Demo setup for user {user_id}")
        
        existing = await db.execute(
            select(func.count(Competitor.id)).where(Competitor.user_id == user_id)
        )
        count = existing.scalar() or 0
        if count > 0:
            return {"message": "Demo data already loaded", "loaded": False}
        
        total_changes = 0
        total_briefs = 0
        
        for comp_data in DEMO_DATA:
            comp = Competitor(
                user_id=user_id,
                name=comp_data["name"],
                website_url=comp_data["website_url"],
                pricing_url=comp_data.get("pricing_url", ""),
                careers_url=comp_data.get("careers_url", ""),
                category=comp_data.get("category", "AI SaaS"),
            )
            db.add(comp)
            await db.flush()
            
            for ch in comp_data.get("changes", []):
                change = Change(
                    competitor_id=comp.id,
                    page_type=ch["page_type"],
                    change_type=ch["change_type"],
                    change_category=ch["change_category"],
                    summary=ch["summary"],
                    details=[{"type": ch["change_type"], "summary": ch["summary"], "significance": ch["significance"]}],
                    significance=ch["significance"],
                )
                db.add(change)
                await db.flush()
                total_changes += 1
                
                report = Report(
                    competitor_id=comp.id,
                    change_id=change.id,
                    report_type="change_brief",
                    title=ch.get("title", ""),
                    what_changed=ch.get("what_changed", ""),
                    why_it_matters=ch.get("why_it_matters", ""),
                    what_to_do=ch.get("what_to_do", ""),
                    threat_level=ch.get("threat_level", ""),
                    full_analysis=ch.get("what_changed", "") + "\n\n" + ch.get("why_it_matters", "") + "\n\n" + ch.get("what_to_do", ""),
                )
                db.add(report)
                total_briefs += 1
        
        await db.commit()
        logger.info(f"Demo loaded: {len(DEMO_DATA)} competitors, {total_changes} changes, {total_briefs} briefs")
        return {
            "message": f"Demo loaded: {len(DEMO_DATA)} competitors, {total_changes} changes, {total_briefs} AI briefs",
            "loaded": True,
            "competitors": len(DEMO_DATA),
            "changes": total_changes,
            "briefs": total_briefs,
        }
    except Exception as e:
        logger.error(f"Demo setup error: {e}")
        logger.error(traceback.format_exc())
        await db.rollback()
        return {"message": f"Error: {str(e)}", "loaded": False}