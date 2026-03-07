from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import Competitor, Change, Report, Snapshot
from pydantic import BaseModel
from typing import Optional
import os
import json
import traceback
from openai import AsyncOpenAI

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    competitor_id: Optional[int] = None


async def _gather_context(db, user_id, competitor_id=None):
    context_parts = []
    query = select(Competitor).where(Competitor.user_id == user_id, Competitor.is_active == True)
    if competitor_id:
        query = query.where(Competitor.id == competitor_id)
    result = await db.execute(query)
    competitors = result.scalars().all()
    if not competitors:
        return "No competitors are being tracked yet."
    for comp in competitors:
        comp_info = f"\n## {comp.name}\n"
        comp_info += f"- Website: {comp.website_url}\n"
        if comp.pricing_url:
            comp_info += f"- Pricing: {comp.pricing_url}\n"
        if comp.careers_url:
            comp_info += f"- Careers: {comp.careers_url}\n"
        if comp.category:
            comp_info += f"- Category: {comp.category}\n"
        changes_result = await db.execute(select(Change).where(Change.competitor_id == comp.id).order_by(desc(Change.detected_at)).limit(10))
        changes = changes_result.scalars().all()
        if changes:
            comp_info += f"\n### Recent Changes:\n"
            for ch in changes:
                comp_info += f"- [{ch.change_type}] {ch.summary or 'No summary'}"
                if ch.significance:
                    comp_info += f" (significance: {ch.significance}/10)"
                comp_info += "\n"
        reports_result = await db.execute(select(Report).where(Report.competitor_id == comp.id).order_by(desc(Report.created_at)).limit(5))
        reports = reports_result.scalars().all()
        if reports:
            comp_info += f"\n### AI Reports:\n"
            for rpt in reports:
                comp_info += f"\n**{rpt.title or rpt.report_type}**\n"
                if rpt.what_changed:
                    comp_info += f"What changed: {rpt.what_changed[:300]}\n"
                if rpt.why_it_matters:
                    comp_info += f"Why it matters: {rpt.why_it_matters[:300]}\n"
                if rpt.what_to_do:
                    comp_info += f"Action: {rpt.what_to_do[:300]}\n"
                if rpt.threat_level:
                    comp_info += f"Threat: {rpt.threat_level}\n"
        snapshots_result = await db.execute(select(Snapshot).where(Snapshot.competitor_id == comp.id, Snapshot.status == "success").order_by(desc(Snapshot.scraped_at)).limit(5))
        snapshots = snapshots_result.scalars().all()
        if snapshots:
            comp_info += f"\n### Snapshots:\n"
            for snap in snapshots:
                comp_info += f"- {snap.page_type} ({snap.url})\n"
                if snap.raw_text:
                    comp_info += f"  Preview: {snap.raw_text[:400]}...\n"
        context_parts.append(comp_info)
    return "\n".join(context_parts)


@router.post("/ask")
async def chat_ask(request: ChatRequest, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return JSONResponse(status_code=500, content={"error": "OpenAI API key not configured"})
        context = await _gather_context(db, current_user["user_id"], request.competitor_id)
        sources = []
        if "Recent Changes" in context:
            sources.append("changes")
        if "AI Reports" in context:
            sources.append("reports")
        if "Snapshots" in context:
            sources.append("snapshots")
        system_prompt = "You are CompetitorRadar AI Assistant. You help users understand their competitive landscape using collected data. Be concise, insightful, and actionable. Use bullet points when comparing. If data is limited, say so honestly."
        user_prompt = f"Competitive intelligence data:\n\n{context}\n\n---\n\nUser question: {request.message}\n\nProvide a helpful, data-driven answer."
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], max_tokens=1000, temperature=0.7)
        reply = response.choices[0].message.content.strip()
        return {"reply": reply, "sources_used": sources}
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Chat Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.get("/suggestions")
async def get_suggestions(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        result = await db.execute(select(Competitor).where(Competitor.user_id == current_user["user_id"], Competitor.is_active == True))
        competitors = result.scalars().all()
        names = [c.name for c in competitors]
        suggestions = ["What are the biggest competitive threats right now?", "Summarize all recent changes across my competitors", "Which competitor is most active lately?"]
        if len(names) >= 2:
            suggestions.append(f"Compare {names[0]} vs {names[1]}")
        if names:
            suggestions.append(f"What is {names[0]} doing with their pricing?")
        suggestions.append("What opportunities am I missing?")
        suggestions.append("Give me a weekly competitive briefing")
        return {"suggestions": suggestions[:8]}
    except Exception:
        return {"suggestions": ["What are the biggest competitive threats?", "Summarize recent changes", "Which competitor should I watch?"]}