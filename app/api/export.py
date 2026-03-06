from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.config import settings
from app.models.models import Report, Competitor
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def verify_token(token):
    try:
        from jose import jwt
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return int(payload.get("sub"))
    except Exception as e:
        logger.error(f"Token error: {e}")
        return None

def build_brief_pdf(report, comp_name):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25*mm, rightMargin=25*mm, topMargin=25*mm, bottomMargin=25*mm)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Title'], fontSize=20, textColor=HexColor('#6366f1'), spaceAfter=6)
    ss = ParagraphStyle('S', parent=styles['Normal'], fontSize=10, textColor=HexColor('#64748b'), spaceAfter=20)
    hs = ParagraphStyle('H', parent=styles['Heading2'], fontSize=13, textColor=HexColor('#6366f1'), spaceBefore=16, spaceAfter=8)
    bs = ParagraphStyle('B', parent=styles['Normal'], fontSize=11, textColor=HexColor('#1e293b'), leading=16, spaceAfter=10)
    elements = []
    elements.append(Paragraph("CompetitorRadar AI", ts))
    elements.append(Paragraph("Strategic Brief - " + comp_name, ss))
    elements.append(Spacer(1, 10))
    if report.title:
        elements.append(Paragraph(report.title, ParagraphStyle('BT', parent=styles['Heading1'], fontSize=16, textColor=HexColor('#0f172a'))))
    for title, content in [("WHAT CHANGED", report.what_changed), ("WHY IT MATTERS", report.why_it_matters), ("WHAT TO DO", report.what_to_do), ("THREAT LEVEL", report.threat_level)]:
        if content:
            elements.append(Paragraph(title, hs))
            for line in content.split('\n'):
                if line.strip():
                    elements.append(Paragraph(line.strip(), bs))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("comp-radar.com", ParagraphStyle('F', parent=styles['Normal'], fontSize=8, textColor=HexColor('#94a3b8'))))
    doc.build(elements)
    buf.seek(0)
    return buf.read()

@router.get("/brief/{report_id}")
async def export_brief_pdf(report_id: int, token: str = "", db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        return Response(content="Invalid token", status_code=401)
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        return Response(content="Not found", status_code=404)
    comp_result = await db.execute(select(Competitor).where(Competitor.id == report.competitor_id))
    comp = comp_result.scalar_one_or_none()
    name = comp.name if comp else "Unknown"
    pdf = build_brief_pdf(report, name)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Brief_" + name.replace(' ','_') + ".pdf"})

@router.get("/all")
async def export_all(token: str = "", db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        return Response(content="Invalid token", status_code=401)
    result = await db.execute(select(Report, Competitor.name).join(Competitor).where(Competitor.user_id == user_id).order_by(Report.created_at.desc()))
    rows = result.all()
    if not rows:
        return Response(content="No reports", status_code=404)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25*mm, rightMargin=25*mm, topMargin=25*mm, bottomMargin=25*mm)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Title'], fontSize=20, textColor=HexColor('#6366f1'), spaceAfter=6)
    hs = ParagraphStyle('H', parent=styles['Heading2'], fontSize=13, textColor=HexColor('#6366f1'), spaceBefore=16, spaceAfter=8)
    bs = ParagraphStyle('B', parent=styles['Normal'], fontSize=11, textColor=HexColor('#1e293b'), leading=16, spaceAfter=10)
    cs = ParagraphStyle('C', parent=styles['Heading1'], fontSize=16, textColor=HexColor('#0f172a'), spaceBefore=30)
    elements = []
    elements.append(Paragraph("CompetitorRadar - All Briefs", ts))
    for report, comp_name in rows:
        elements.append(Paragraph(comp_name + " - " + (report.title or 'Brief'), cs))
        for title, content in [("WHAT CHANGED", report.what_changed), ("WHY IT MATTERS", report.why_it_matters), ("WHAT TO DO", report.what_to_do), ("THREAT LEVEL", report.threat_level)]:
            if content:
                elements.append(Paragraph(title, hs))
                for line in content.split('\n'):
                    if line.strip():
                        elements.append(Paragraph(line.strip(), bs))
    doc.build(elements)
    buf.seek(0)
    return Response(content=buf.read(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=All_Briefs.pdf"})