from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Competitor, Snapshot
from app.services.seo_tracker import analyze_seo
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/analyze/{competitor_id}")
async def analyze_competitor_seo(competitor_id: int, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    comp = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    comp = comp.scalar_one_or_none()
    if not comp:
        return {"error": "Competitor not found"}
    
    snapshots = await db.execute(
        select(Snapshot).where(Snapshot.competitor_id == competitor_id)
        .order_by(Snapshot.scraped_at.desc()).limit(5)
    )
    snaps = snapshots.scalars().all()
    
    results = []
    for snap in snaps:
        if snap.content_data:
            seo = analyze_seo(snap.content_data, snap.url)
            seo["page_type"] = snap.page_type
            seo["scanned_at"] = str(snap.scraped_at)
            results.append(seo)
    
    return {"competitor": comp.name, "website": comp.website_url, "seo_analysis": results}

@router.get("/overview")
async def seo_overview(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    comps = await db.execute(select(Competitor).where(Competitor.user_id == current_user["user_id"]))
    competitors = comps.scalars().all()
    
    overview = []
    for comp in competitors:
        snap = await db.execute(
            select(Snapshot).where(Snapshot.competitor_id == comp.id)
            .where(Snapshot.page_type == "homepage")
            .order_by(Snapshot.scraped_at.desc()).limit(1)
        )
        snap = snap.scalar_one_or_none()
        if snap and snap.content_data:
            seo = analyze_seo(snap.content_data, snap.url)
            overview.append({"competitor": comp.name, "url": comp.website_url, "overall_score": seo["overall_score"], "title_score": seo["title"]["score"], "meta_score": seo["meta_description"]["score"], "heading_score": seo["headings"]["score"], "content_score": seo["content"]["score"], "word_count": seo["content"]["word_count"], "keywords": seo["keywords"][:5]})
    
    return overview