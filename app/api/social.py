from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import User, Competitor, SocialPost
from app.services.social_tracker import scan_competitor_social, seed_demo_social_posts
from pydantic import BaseModel
from typing import Optional
import traceback

router = APIRouter(prefix="/social", tags=["social"])


class SocialSettingsUpdate(BaseModel):
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    reddit_keywords: Optional[str] = None


@router.get("/summary")
async def get_social_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        comp_result = await db.execute(
            select(Competitor).where(
                Competitor.user_id == current_user["user_id"],
                Competitor.is_active == True
            )
        )
        competitors = comp_result.scalars().all()
        comp_ids = [c.id for c in competitors]
        comp_map = {c.id: c.name for c in competitors}

        if not comp_ids:
            return {
                "total_posts": 0,
                "announcements": 0,
                "by_platform": {},
                "recent_posts": [],
                "by_sentiment": {}
            }

        posts_result = await db.execute(
            select(SocialPost).where(
                SocialPost.competitor_id.in_(comp_ids)
            ).order_by(desc(SocialPost.detected_at)).limit(50)
        )
        posts = posts_result.scalars().all()

        by_platform = {}
        by_sentiment = {}
        announcements = 0
        recent_posts = []

        for p in posts:
            by_platform[p.platform] = by_platform.get(p.platform, 0) + 1
            by_sentiment[p.sentiment or "neutral"] = by_sentiment.get(p.sentiment or "neutral", 0) + 1
            if p.is_announcement:
                announcements += 1
            if len(recent_posts) < 20:
                recent_posts.append({
                    "id": p.id,
                    "competitor_id": p.competitor_id,
                    "competitor_name": comp_map.get(p.competitor_id, "Unknown"),
                    "platform": p.platform,
                    "content": (p.content or "")[:280],
                    "sentiment": p.sentiment or "neutral",
                    "is_announcement": p.is_announcement or False,
                    "ai_summary": p.ai_summary,
                    "posted_at": p.posted_at.isoformat() if p.posted_at else None,
                    "post_url": p.post_url,
                    "engagement": p.engagement or {},
                    "author": p.author
                })

        return {
            "total_posts": len(posts),
            "announcements": announcements,
            "by_platform": by_platform,
            "by_sentiment": by_sentiment,
            "recent_posts": recent_posts
        }
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Social Summary Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )


@router.get("/posts/{competitor_id}")
async def get_competitor_posts(
    competitor_id: int,
    platform: Optional[str] = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        comp = await db.execute(
            select(Competitor).where(
                Competitor.id == competitor_id,
                Competitor.user_id == current_user["user_id"]
            )
        )
        if not comp.scalar_one_or_none():
            raise HTTPException(404, "Competitor not found")

        query = select(SocialPost).where(
            SocialPost.competitor_id == competitor_id
        )
        if platform:
            query = query.where(SocialPost.platform == platform)

        result = await db.execute(
            query.order_by(desc(SocialPost.posted_at)).limit(limit)
        )
        posts = result.scalars().all()

        return [{
            "id": p.id,
            "platform": p.platform,
            "content": p.content,
            "post_url": p.post_url,
            "author": p.author,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "engagement": p.engagement or {},
            "sentiment": p.sentiment or "neutral",
            "is_announcement": p.is_announcement or False,
            "ai_summary": p.ai_summary,
            "detected_at": p.detected_at.isoformat() if p.detected_at else None
        } for p in posts]
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Social Posts Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )


@router.post("/scan/{competitor_id}")
async def scan_social(
    competitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Competitor).where(
                Competitor.id == competitor_id,
                Competitor.user_id == current_user["user_id"]
            )
        )
        competitor = result.scalar_one_or_none()
        if not competitor:
            raise HTTPException(404, "Competitor not found")

        new_posts = await scan_competitor_social(competitor, db)
        return {
            "new_posts": new_posts,
            "message": f"Found {new_posts} new posts"
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Social Scan Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )


@router.post("/scan-all")
async def scan_all_social(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        comp_result = await db.execute(
            select(Competitor).where(
                Competitor.user_id == current_user["user_id"],
                Competitor.is_active == True
            )
        )
        competitors = comp_result.scalars().all()
        total_new = 0
        results = []

        for comp in competitors:
            try:
                n = await scan_competitor_social(comp, db)
                total_new += n
                results.append({"competitor": comp.name, "new_posts": n})
            except Exception as e:
                print(f"[Scan-All] Error scanning {comp.name}: {e}")
                results.append({"competitor": comp.name, "error": str(e)})

        return {
            "total_new_posts": total_new,
            "results": results
        }
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Scan-All Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )


@router.post("/seed-demo")
async def seed_demo_data(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Seed demo social posts for all competitors when live APIs are blocked."""
    try:
        comp_result = await db.execute(
            select(Competitor).where(
                Competitor.user_id == current_user["user_id"],
                Competitor.is_active == True
            )
        )
        competitors = comp_result.scalars().all()
        total_new = 0

        for comp in competitors:
            try:
                n = await seed_demo_social_posts(comp, db)
                total_new += n
            except Exception as e:
                print(f"[Seed Demo] Error for {comp.name}: {e}")

        return {
            "message": f"Seeded {total_new} demo posts",
            "total_new_posts": total_new
        }
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Seed Demo Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )


@router.put("/settings/{competitor_id}")
async def update_social_settings(
    competitor_id: int,
    settings: SocialSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Competitor).where(
                Competitor.id == competitor_id,
                Competitor.user_id == current_user["user_id"]
            )
        )
        competitor = result.scalar_one_or_none()
        if not competitor:
            raise HTTPException(404, "Competitor not found")

        if settings.twitter_handle is not None:
            handle = settings.twitter_handle.strip().lstrip("@")
            competitor.twitter_handle = handle or None
        if settings.linkedin_url is not None:
            url = settings.linkedin_url.strip()
            competitor.linkedin_url = url or None
        if settings.reddit_keywords is not None:
            keywords = settings.reddit_keywords.strip()
            competitor.reddit_keywords = keywords or None

        await db.commit()

        return {
            "message": "Social settings updated",
            "twitter_handle": competitor.twitter_handle,
            "linkedin_url": competitor.linkedin_url,
            "reddit_keywords": competitor.reddit_keywords
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Settings Update Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )


@router.get("/settings/{competitor_id}")
async def get_social_settings(
    competitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Competitor).where(
                Competitor.id == competitor_id,
                Competitor.user_id == current_user["user_id"]
            )
        )
        competitor = result.scalar_one_or_none()
        if not competitor:
            raise HTTPException(404, "Competitor not found")

        return {
            "id": competitor.id,
            "name": competitor.name,
            "twitter_handle": competitor.twitter_handle or "",
            "linkedin_url": competitor.linkedin_url or "",
            "reddit_keywords": competitor.reddit_keywords or competitor.name
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(f"[Settings Get Error] {error_msg}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": tb}
        )
@router.delete("/cleanup-spam")
async def cleanup_spam(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        from sqlalchemy import or_, func
        spam_words = ['onlyfans', 'porn', 'xxx', 'nsfw', 'nude', 'naked', 'brazzers', 'pussy', 'cock', 'hentai', 'milf', 'escort', 'cam girl', 'adult content', 'removed by reddit']
        conditions = [func.lower(SocialPost.content).contains(word) for word in spam_words]
        result = await db.execute(select(SocialPost).where(or_(*conditions)))
        spam_posts = result.scalars().all()
        count = len(spam_posts)
        for post in spam_posts:
            await db.delete(post)
        if count:
            await db.commit()
        return {"message": f"Deleted {count} spam posts"}
    except Exception as e:
        import traceback
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})