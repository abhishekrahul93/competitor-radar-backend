"""
Competitor CRUD routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Competitor, Change, Snapshot

router = APIRouter()

class CompetitorCreate(BaseModel):
    name: str
    website_url: str
    pricing_url: Optional[str] = None
    careers_url: Optional[str] = None
    github_url: Optional[str] = None
    docs_url: Optional[str] = None
    category: str = "general"

class CompetitorResponse(BaseModel):
    id: int
    name: str
    website_url: str
    pricing_url: Optional[str]
    careers_url: Optional[str]
    github_url: Optional[str]
    docs_url: Optional[str]
    category: str
    is_active: bool
    changes_count: int = 0
    last_scanned: Optional[str] = None

@router.get("/")
async def list_competitors(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Competitor)
        .where(Competitor.user_id == current_user["user_id"])
        .where(Competitor.is_active == True)
        .order_by(Competitor.name)
    )
    competitors = result.scalars().all()
    
    response = []
    for comp in competitors:
        # Get change count
        change_count = await db.execute(
            select(func.count(Change.id)).where(Change.competitor_id == comp.id)
        )
        count = change_count.scalar() or 0
        
        # Get last scan time
        last_snap = await db.execute(
            select(Snapshot.scraped_at)
            .where(Snapshot.competitor_id == comp.id)
            .order_by(Snapshot.scraped_at.desc())
            .limit(1)
        )
        last_scan = last_snap.scalar_one_or_none()
        
        response.append({
            "id": comp.id,
            "name": comp.name,
            "website_url": comp.website_url,
            "pricing_url": comp.pricing_url,
            "careers_url": comp.careers_url,
            "github_url": comp.github_url,
            "docs_url": comp.docs_url,
            "category": comp.category,
            "is_active": comp.is_active,
            "changes_count": count,
            "last_scanned": str(last_scan) if last_scan else None,
        })
    
    return response

@router.post("/")
async def create_competitor(
    data: CompetitorCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Clean URLs
    website_url = data.website_url
    if not website_url.startswith("http"):
        website_url = "https://" + website_url
    
    comp = Competitor(
        user_id=current_user["user_id"],
        name=data.name,
        website_url=website_url,
        pricing_url=data.pricing_url,
        careers_url=data.careers_url,
        github_url=data.github_url,
        docs_url=data.docs_url,
        category=data.category,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    
    return {"id": comp.id, "name": comp.name, "message": f"Now tracking {comp.name}"}

@router.get("/{competitor_id}")
async def get_competitor(
    competitor_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Competitor)
        .where(Competitor.id == competitor_id)
        .where(Competitor.user_id == current_user["user_id"])
    )
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return comp

@router.delete("/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Competitor)
        .where(Competitor.id == competitor_id)
        .where(Competitor.user_id == current_user["user_id"])
    )
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    comp.is_active = False
    await db.commit()
    return {"message": f"Stopped tracking {comp.name}"}
