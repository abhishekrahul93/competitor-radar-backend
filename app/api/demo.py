"""
Demo data — pre-loads sample competitors and AI briefs for new users.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Competitor, Change, Report

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
                "brief": {
                    "title": "Jasper AI — pricing changes detected",
                    "what_changed": "Jasper raised their Pro plan from $39/month to $49/month — a 26% price hike. They also launched a new Business plan at $69/month with team features, brand voice, and API access.",
                    "why_it_matters": "This signals Jasper is moving upmarket aggressively. The price increase will push budget-conscious users to seek alternatives. The new Business tier shows they are targeting mid-market teams, not just individual creators.",
                    "what_to_do": "1. Maintain your current pricing to capture unhappy Jasper users migrating from the price hike.\n2. Create comparison content targeting 'Jasper alternative' and 'Jasper pricing 2026' keywords.\n3. Monitor Jasper reviews on G2 and Twitter for the next 30 days — users will be vocal about the increase.",
                    "threat_level": "HIGH — Pricing creates immediate acquisition opportunity",
                }
            },
            {
                "page_type": "careers",
                "change_type": "jobs_added",
                "change_category": "hiring",
                "summary": "4 new ML Engineer positions posted focused on multimodal AI and computer vision.",
                "significance": 0.82,
                "brief": {
                    "title": "Jasper AI — careers changes detected",
                    "what_changed": "Jasper posted 4 new roles: 2 Senior ML Engineers (multimodal AI), 1 Computer Vision Lead, 1 Research Scientist (image generation). All SF-based, $200-350K salary range.",
                    "why_it_matters": "Jasper is building in-house multimodal capabilities — text + image + likely video. The Computer Vision hire means they are building proprietary models instead of relying solely on OpenAI. This could create a significant product moat in 6-12 months.",
                    "what_to_do": "1. Evaluate your own multimodal roadmap. If you are not planning image features, you will fall behind in 2-3 quarters.\n2. Partner with an existing image AI provider to ship multimodal faster than Jasper can build in-house.\n3. Track their GitHub activity and research blog for early signals of what they are building.",
                    "threat_level": "HIGH — Signals product expansion that redefines competitive landscape",
                }
            }
        ]
    },
    {
        "name": "Copy.ai",
        "website_url": "https://copy.ai",
        "pricing_url": "https://copy.ai/pricing",
        "careers_url": "https://copy.ai/careers",
        "category": "AI SaaS",
        "changes": [
            {
                "page_type": "homepage",
                "change_type": "title_change",
                "change_category": "messaging",
                "summary": "Homepage repositioned from 'AI Content Platform' to 'AI Sales Agent That Closes Deals'.",
                "significance": 0.72,
                "brief": {
                    "title": "Copy.ai — homepage changes detected",
                    "what_changed": "Copy.ai changed their primary headline from 'AI-Powered Content Platform' to 'The AI Sales Agent That Closes Deals.' They added sales workflow sections, CRM integrations, and ROI calculators. The word 'content' appears 60% less on their homepage.",
                    "why_it_matters": "Copy.ai is pivoting from content generation to sales automation. They are exiting the crowded AI writing space for AI sales tech — a market with higher willingness-to-pay and faster growth. Their content-focused customers will start churning.",
                    "what_to_do": "1. Copy.ai is becoming less of a direct competitor in content. Sharpen your positioning in the content space.\n2. Their content-focused customers will start churning — create targeted campaigns to capture them.\n3. Evaluate whether sales-adjacent features could expand your own market.",
                    "threat_level": "MEDIUM — Reduces direct competition but signals market shift",
                }
            }
        ]
    },
    {
        "name": "Writesonic",
        "website_url": "https://writesonic.com",
        "pricing_url": "https://writesonic.com/pricing",
        "careers_url": "https://writesonic.com/careers",
        "category": "AI SaaS",
        "changes": [
            {
                "page_type": "pricing",
                "change_type": "pricing_change",
                "change_category": "pricing",
                "summary": "Pro plan price increased from $19/mo to $29/mo. Free tier reduced from 10K to 2.5K words.",
                "significance": 0.95,
                "brief": {
                    "title": "Writesonic — pricing changes detected",
                    "what_changed": "Writesonic raised their Pro plan from $19/month to $29/month — a 53% price hike. They renamed Pro to Professional and added AI image generation. Free tier was cut from 10,000 to 2,500 words/month.",
                    "why_it_matters": "This signals Writesonic is moving upmarket. The free tier cut forces more users into paid plans. Combined with their new Enterprise tier, they are executing a classic upmarket move. Any competitor at the old $19 price point now has a major acquisition advantage.",
                    "what_to_do": "1. Maintain your current pricing to capture unhappy Writesonic users.\n2. Monitor Writesonic reviews on G2 and Twitter for the next 30 days — their users will be vocal.\n3. Target 'Writesonic alternative' and 'Writesonic pricing' in SEO. Traffic on these terms will spike.",
                    "threat_level": "HIGH — Pricing creates immediate acquisition opportunity",
                }
            },
            {
                "page_type": "homepage",
                "change_type": "headings_added",
                "change_category": "messaging",
                "summary": "New Enterprise tier added with SOC 2 Type II compliance badge prominently displayed.",
                "significance": 0.72,
                "brief": {
                    "title": "Writesonic — homepage changes detected",
                    "what_changed": "Writesonic launched an Enterprise tier with custom pricing, SSO, dedicated support, API access, and SLA guarantees. A SOC 2 Type II badge now appears on homepage and pricing page.",
                    "why_it_matters": "Writesonic is targeting enterprise aggressively. SOC 2 compliance is expensive and takes 6+ months — this shows serious commitment. Combined with their price hike, they are leaving the SMB space for bigger contracts.",
                    "what_to_do": "1. If enterprise is not your target, celebrate — Writesonic is leaving the SMB space.\n2. If you do target enterprise, SOC 2 is becoming table stakes. Start your compliance timeline.\n3. Marketing angle: 'Built for creators, not committees.'",
                    "threat_level": "MEDIUM — Enterprise shift reduces SMB competition",
                }
            }
        ]
    }
]

@router.post("/setup")
async def setup_demo(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user["user_id"]
    
    existing = await db.execute(
        select(func.count(Competitor.id)).where(Competitor.user_id == user_id)
    )
    if existing.scalar() > 0:
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
            
            brief = ch.get("brief", {})
            report = Report(
                competitor_id=comp.id,
                change_id=change.id,
                report_type="change_brief",
                title=brief.get("title", ""),
                what_changed=brief.get("what_changed", ""),
                why_it_matters=brief.get("why_it_matters", ""),
                what_to_do=brief.get("what_to_do", ""),
                threat_level=brief.get("threat_level", ""),
                full_analysis=f"{brief.get('what_changed', '')}\n\n{brief.get('why_it_matters', '')}\n\n{brief.get('what_to_do', '')}",
            )
            db.add(report)
            total_briefs += 1
    
    await db.commit()
    return {
        "message": f"Demo loaded: {len(DEMO_DATA)} competitors, {total_changes} changes, {total_briefs} AI briefs",
        "loaded": True,
        "competitors": len(DEMO_DATA),
        "changes": total_changes,
        "briefs": total_briefs,
    }