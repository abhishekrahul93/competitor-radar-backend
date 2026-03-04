"""
Changes API — list and filter detected changes.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Change, Competitor

router = APIRouter()

@router.get("/")
async def list_changes(
    limit: int = Query(20, le=100),
    competitor_id: Optional[int] = None,
    min_significance: float = Query(0.0, ge=0.0, le=1.0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Change, Competitor.name.label("competitor_name"))
        .join(Competitor)
        .where(Competitor.user_id == current_user["user_id"])
        .where(Change.significance >= min_significance)
        .order_by(desc(Change.detected_at))
        .limit(limit)
    )
    
    if competitor_id:
        query = query.where(Change.competitor_id == competitor_id)
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "id": change.id,
            "competitor_id": change.competitor_id,
            "competitor_name": comp_name,
            "page_type": change.page_type,
            "change_type": change.change_type,
            "change_category": change.change_category,
            "summary": change.summary,
            "details": change.details,
            "significance": change.significance,
            "detected_at": str(change.detected_at),
        }
        for change, comp_name in rows
    ]
