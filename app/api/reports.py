"""
Reports API — AI-generated intelligence briefs.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Report, Competitor

router = APIRouter()

@router.get("/")
async def list_reports(
    limit: int = Query(20, le=100),
    competitor_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Report, Competitor.name.label("competitor_name"))
        .join(Competitor, isouter=True)
        .where(Competitor.user_id == current_user["user_id"])
        .order_by(desc(Report.created_at))
        .limit(limit)
    )
    
    if competitor_id:
        query = query.where(Report.competitor_id == competitor_id)
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "id": report.id,
            "competitor_id": report.competitor_id,
            "competitor_name": comp_name,
            "change_id": report.change_id,
            "report_type": report.report_type,
            "title": report.title,
            "what_changed": report.what_changed,
            "why_it_matters": report.why_it_matters,
            "what_to_do": report.what_to_do,
            "threat_level": report.threat_level,
            "full_analysis": report.full_analysis,
            "created_at": str(report.created_at),
        }
        for report, comp_name in rows
    ]

@router.get("/{report_id}")
async def get_report(
    report_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Report, Competitor.name.label("competitor_name"))
        .join(Competitor, isouter=True)
        .where(Report.id == report_id)
        .where(Competitor.user_id == current_user["user_id"])
    )
    row = result.first()
    if not row:
        return {"error": "Report not found"}
    
    report, comp_name = row
    return {
        "id": report.id,
        "competitor_name": comp_name,
        "title": report.title,
        "what_changed": report.what_changed,
        "why_it_matters": report.why_it_matters,
        "what_to_do": report.what_to_do,
        "threat_level": report.threat_level,
        "full_analysis": report.full_analysis,
        "created_at": str(report.created_at),
    }
