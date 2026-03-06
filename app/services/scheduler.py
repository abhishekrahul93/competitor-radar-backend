"""
Auto-scheduler — scans every 12 hours + weekly digest every Monday.
"""
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.models import Competitor, Snapshot, Change, Report, User
from app.services.scraper import fetch_page, extract_content, compute_content_hash
from app.services.change_detector import detect_changes
from app.services.ai_analyst import generate_brief
from app.services.email_service import send_change_alert, send_weekly_digest

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def scan_all_users():
    logger.info("=== AUTO-SCAN STARTED ===")
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Competitor).where(Competitor.is_active == True))
            competitors = result.scalars().all()
            if not competitors:
                return
            total = 0
            for comp in competitors:
                try:
                    total += await _scan_single(comp, db)
                except Exception as e:
                    logger.error(f"Error scanning {comp.name}: {e}")
            await db.commit()
            logger.info(f"=== AUTO-SCAN COMPLETE: {len(competitors)} competitors, {total} changes ===")
        except Exception as e:
            logger.error(f"Auto-scan failed: {e}")

async def _scan_single(comp, db):
    changes_found = 0
    pages = []
    if comp.website_url:
        pages.append(("homepage", comp.website_url))
    if comp.pricing_url:
        pages.append(("pricing", comp.pricing_url))
    if comp.careers_url:
        pages.append(("careers", comp.careers_url))
    for page_type, url in pages:
        try:
            response = await fetch_page(url)
            if not response["success"]:
                continue
            content = extract_content(response["html"], page_type)
            content_hash = compute_content_hash(content)
            prev = await db.execute(
                select(Snapshot).where(Snapshot.competitor_id == comp.id)
                .where(Snapshot.page_type == page_type)
                .order_by(Snapshot.scraped_at.desc()).limit(1)
            )
            prev_snapshot = prev.scalar_one_or_none()
            snapshot = Snapshot(competitor_id=comp.id, page_type=page_type, url=url,
                content_hash=content_hash, content_data=content,
                raw_text=content.get("full_text", "")[:10000], status="success")
            db.add(snapshot)
            if prev_snapshot and prev_snapshot.content_hash != content_hash:
                old_content = prev_snapshot.content_data or {}
                changes = detect_changes(old_content, content, page_type)
                if changes:
                    max_sig = max(c.get("significance", 0) for c in changes)
                    summary = "; ".join(c["summary"] for c in changes[:3])
                    change_record = Change(competitor_id=comp.id, page_type=page_type,
                        change_type=changes[0]["type"], change_category=changes[0].get("category", ""),
                        summary=summary, details=changes, significance=max_sig)
                    db.add(change_record)
                    await db.flush()
                    changes_found += len(changes)
                    brief = await generate_brief(comp.name, page_type, changes)
                    report = Report(competitor_id=comp.id, change_id=change_record.id,
                        report_type="change_brief",
                        title=f"[AUTO] {comp.name} - {page_type} changes",
                        what_changed=brief.get("what_changed", ""),
                        why_it_matters=brief.get("why_it_matters", ""),
                        what_to_do=brief.get("what_to_do", ""),
                        threat_level=brief.get("threat_level", ""),
                        full_analysis=brief.get("full_analysis", ""))
                    db.add(report)
                    await send_change_alert(comp.name, page_type, changes, brief)
        except Exception as e:
            logger.error(f"Error: {comp.name}/{page_type}: {e}")
    return changes_found


async def send_weekly_digest_job():
    """Collect all changes from the past 7 days and send digest email."""
    logger.info("=== WEEKLY DIGEST STARTED ===")
    async with AsyncSessionLocal() as db:
        try:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            result = await db.execute(
                select(Change, Competitor.name)
                .join(Competitor)
                .where(Change.detected_at >= week_ago)
                .order_by(Change.significance.desc())
            )
            rows = result.all()
            
            if not rows:
                logger.info("No changes this week - skipping digest")
                return
            
            changes_by_competitor = {}
            total_changes = 0
            
            for change, comp_name in rows:
                total_changes += 1
                if comp_name not in changes_by_competitor:
                    changes_by_competitor[comp_name] = {
                        "count": 0,
                        "max_significance": 0,
                        "top_change": "",
                    }
                changes_by_competitor[comp_name]["count"] += 1
                if change.significance > changes_by_competitor[comp_name]["max_significance"]:
                    changes_by_competitor[comp_name]["max_significance"] = change.significance
                    changes_by_competitor[comp_name]["top_change"] = change.summary or ""
            
            # Count briefs
            brief_result = await db.execute(
                select(Report).where(Report.created_at >= week_ago)
            )
            total_briefs = len(brief_result.scalars().all())
            
            await send_weekly_digest(changes_by_competitor, total_changes, total_briefs)
            logger.info(f"=== WEEKLY DIGEST SENT: {total_changes} changes ===")
            
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")


def start_scheduler(interval_hours=12):
    # Auto-scan every 12 hours
    scheduler.add_job(scan_all_users, trigger=IntervalTrigger(hours=interval_hours),
        id="auto_scan", name="Auto-scan", replace_existing=True)
    
    # Weekly digest every Monday at 8 AM UTC
    scheduler.add_job(send_weekly_digest_job, trigger=CronTrigger(day_of_week='mon', hour=8),
        id="weekly_digest", name="Weekly digest", replace_existing=True)
    
    scheduler.start()
    logger.info(f"Scheduler started - scan every {interval_hours}h, weekly digest Monday 8AM UTC")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()