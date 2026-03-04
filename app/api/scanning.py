"""
Scanning route — triggers scraping, change detection, and AI analysis.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Competitor, Snapshot, Change, Report
from app.services.scraper import fetch_page, extract_content, compute_content_hash
from app.services.change_detector import detect_changes
from app.services.ai_analyst import generate_brief

router = APIRouter()

@router.post("/all")
async def scan_all(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Scan all active competitors."""
    result = await db.execute(
        select(Competitor)
        .where(Competitor.user_id == current_user["user_id"])
        .where(Competitor.is_active == True)
    )
    competitors = result.scalars().all()
    
    if not competitors:
        raise HTTPException(status_code=400, detail="No competitors to scan. Add some first!")
    
    results = []
    for comp in competitors:
        comp_result = await _scan_competitor(comp, db)
        results.append(comp_result)
    
    total_changes = sum(r.get("changes_found", 0) for r in results)
    return {
        "message": f"Scanned {len(competitors)} competitors. {total_changes} changes found.",
        "results": results,
    }

@router.post("/{competitor_id}")
async def scan_one(
    competitor_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Scan a specific competitor."""
    result = await db.execute(
        select(Competitor)
        .where(Competitor.id == competitor_id)
        .where(Competitor.user_id == current_user["user_id"])
    )
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    scan_result = await _scan_competitor(comp, db)
    return scan_result


async def _scan_competitor(comp: Competitor, db: AsyncSession) -> dict:
    """Internal: scan a single competitor across all tracked pages."""
    pages = []
    if comp.website_url:
        pages.append(("homepage", comp.website_url))
    if comp.pricing_url:
        pages.append(("pricing", comp.pricing_url))
    if comp.careers_url:
        pages.append(("careers", comp.careers_url))
    if comp.docs_url:
        pages.append(("docs", comp.docs_url))
    
    result = {
        "competitor": comp.name,
        "competitor_id": comp.id,
        "pages_scanned": 0,
        "changes_found": 0,
        "errors": [],
        "briefs": [],
    }
    
    for page_type, url in pages:
        try:
            # Fetch page
            response = await fetch_page(url)
            if not response["success"]:
                result["errors"].append(f"{page_type}: {response.get('error', 'failed')}")
                continue
            
            # Extract content
            content = extract_content(response["html"], page_type)
            content_hash = compute_content_hash(content)
            content_json = json.dumps(content)
            
            # Get previous snapshot
            prev = await db.execute(
                select(Snapshot)
                .where(Snapshot.competitor_id == comp.id)
                .where(Snapshot.page_type == page_type)
                .order_by(Snapshot.scraped_at.desc())
                .limit(1)
            )
            prev_snapshot = prev.scalar_one_or_none()
            
            # Save new snapshot
            snapshot = Snapshot(
                competitor_id=comp.id,
                page_type=page_type,
                url=url,
                content_hash=content_hash,
                content_data=content,
                raw_text=content.get("full_text", "")[:10000],
                status="success",
            )
            db.add(snapshot)
            result["pages_scanned"] += 1
            
            # Detect changes
            if prev_snapshot and prev_snapshot.content_hash != content_hash:
                old_content = prev_snapshot.content_data or {}
                changes = detect_changes(old_content, content, page_type)
                
                if changes:
                    max_sig = max(c.get("significance", 0) for c in changes)
                    summary = "; ".join(c["summary"] for c in changes[:3])
                    
                    change_record = Change(
                        competitor_id=comp.id,
                        page_type=page_type,
                        change_type=changes[0]["type"],
                        change_category=changes[0].get("category", ""),
                        summary=summary,
                        details=changes,
                        significance=max_sig,
                    )
                    db.add(change_record)
                    await db.flush()  # Get the ID
                    
                    result["changes_found"] += len(changes)
                    
                    # Generate AI brief
                    brief = await generate_brief(comp.name, page_type, changes)
                    
                    report = Report(
                        competitor_id=comp.id,
                        change_id=change_record.id,
                        report_type="change_brief",
                        title=f"{comp.name} — {page_type} changes detected",
                        what_changed=brief.get("what_changed", ""),
                        why_it_matters=brief.get("why_it_matters", ""),
                        what_to_do=brief.get("what_to_do", ""),
                        threat_level=brief.get("threat_level", ""),
                        full_analysis=brief.get("full_analysis", ""),
                    )
                    db.add(report)
                    
                    result["briefs"].append({
                        "page_type": page_type,
                        "changes_count": len(changes),
                        "significance": max_sig,
                        "threat_level": brief.get("threat_level", ""),
                    })
        
        except Exception as e:
            result["errors"].append(f"{page_type}: {str(e)}")
    
    await db.commit()
    return result
