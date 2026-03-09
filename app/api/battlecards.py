"""
Battlecard API routes — generate and retrieve AI battlecards.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.battlecard_generator import generate_battlecard
import json

router = APIRouter(prefix="/battlecards", tags=["Battlecards"])


@router.get("/")
async def list_battlecards(user=Depends(get_current_user), db=Depends(get_db)):
    """List all generated battlecards for the user's competitors."""
    try:
        result = await db.execute(
            text("SELECT id, name, website_url FROM competitors WHERE user_id = :uid ORDER BY name"),
            {"uid": user.id},
        )
        competitors = [{"id": r[0], "name": r[1], "website_url": r[2]} for r in result.fetchall()]

        battlecards = []
        for comp in competitors:
            # Get latest changes for this competitor
            changes_result = await db.execute(
                text("SELECT change_category, summary, significance FROM changes WHERE competitor_id = :cid ORDER BY detected_at DESC LIMIT 5"),
                {"cid": comp["id"]},
            )
            changes = [{"change_category": r[0], "summary": r[1], "significance": r[2]} for r in changes_result.fetchall()]

            battlecards.append({
                "competitor_id": comp["id"],
                "competitor_name": comp["name"],
                "website_url": comp["website_url"],
                "changes_count": len(changes),
                "has_data": len(changes) > 0,
            })

        return battlecards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/{competitor_id}")
async def generate(competitor_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    """Generate an AI battlecard for a specific competitor."""
    try:
        # Get competitor
        result = await db.execute(
            text("SELECT id, name, website_url, pricing_url, careers_url FROM competitors WHERE id = :cid AND user_id = :uid"),
            {"cid": competitor_id, "uid": user.id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Competitor not found")

        competitor = {"id": row[0], "name": row[1], "website_url": row[2], "pricing_url": row[3], "careers_url": row[4]}

        # Get recent changes
        changes_result = await db.execute(
            text("SELECT change_category, summary, significance, page_type, detected_at FROM changes WHERE competitor_id = :cid ORDER BY detected_at DESC LIMIT 10"),
            {"cid": competitor_id},
        )
        changes = [{"change_category": r[0], "summary": r[1], "significance": r[2], "page_type": r[3], "detected_at": str(r[4])} for r in changes_result.fetchall()]

        # Get AI briefs
        briefs_result = await db.execute(
            text("SELECT title, what_changed, threat_level FROM reports WHERE competitor_id = :cid ORDER BY created_at DESC LIMIT 5"),
            {"cid": competitor_id},
        )
        briefs = [{"title": r[0], "what_changed": r[1], "threat_level": r[2]} for r in briefs_result.fetchall()]

        # Generate battlecard
        battlecard = await generate_battlecard(competitor, changes, briefs)
        return battlecard

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
