"""
Battlecard API routes — generate and retrieve AI battlecards.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.battlecard_generator import generate_battlecard
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/battlecards", tags=["Battlecards"])


@router.get("/")
async def list_battlecards(user=Depends(get_current_user), db=Depends(get_db)):
    """List all competitors available for battlecard generation."""
    try:
        result = await db.execute(
            text("SELECT id, name, website_url FROM competitors WHERE user_id = :uid ORDER BY name"),
            {"uid": user.id},
        )
        competitors = [{"id": r[0], "name": r[1], "website_url": r[2]} for r in result.fetchall()]

        battlecards = []
        for comp in competitors:
            # Count changes for this competitor
            try:
                count_result = await db.execute(
                    text("SELECT COUNT(*) FROM changes WHERE competitor_id = :cid"),
                    {"cid": comp["id"]},
                )
                count = count_result.scalar() or 0
            except Exception:
                count = 0

            battlecards.append({
                "competitor_id": comp["id"],
                "competitor_name": comp["name"],
                "website_url": comp["website_url"],
                "changes_count": count,
                "has_data": count > 0,
            })

        return battlecards
    except Exception as e:
        logger.error(f"Battlecards list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/{competitor_id}")
async def generate(competitor_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    """Generate an AI battlecard for a specific competitor."""
    try:
        # Get competitor
        result = await db.execute(
            text("SELECT id, name, website_url FROM competitors WHERE id = :cid AND user_id = :uid"),
            {"cid": competitor_id, "uid": user.id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Competitor not found")

        competitor = {"id": row[0], "name": row[1], "website_url": row[2]}

        # Get recent changes — use SELECT * to avoid column name issues
        changes = []
        try:
            changes_result = await db.execute(
                text("SELECT * FROM changes WHERE competitor_id = :cid ORDER BY detected_at DESC LIMIT 10"),
                {"cid": competitor_id},
            )
            rows = changes_result.fetchall()
            columns = changes_result.keys() if hasattr(changes_result, 'keys') else []
            for r in rows:
                row_dict = dict(zip(columns, r)) if columns else {}
                changes.append({
                    "change_category": row_dict.get("change_category", row_dict.get("category", "unknown")),
                    "summary": row_dict.get("summary", ""),
                    "significance": row_dict.get("significance", 0.5),
                    "page_type": row_dict.get("page_type", ""),
                    "detected_at": str(row_dict.get("detected_at", "")),
                })
        except Exception as e:
            logger.error(f"Error fetching changes: {e}")

        # Get AI briefs
        briefs = []
        try:
            briefs_result = await db.execute(
                text("SELECT title, what_changed, threat_level FROM reports WHERE competitor_id = :cid ORDER BY created_at DESC LIMIT 5"),
                {"cid": competitor_id},
            )
            for r in briefs_result.fetchall():
                briefs.append({"title": r[0], "what_changed": r[1], "threat_level": r[2]})
        except Exception as e:
            logger.error(f"Error fetching briefs: {e}")

        # Generate battlecard
        battlecard = await generate_battlecard(competitor, changes, briefs)
        return battlecard

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Battlecard generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
