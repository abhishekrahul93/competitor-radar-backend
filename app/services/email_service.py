"""
Email alert service — sends notifications when competitor changes detected.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_change_alert(competitor_name, page_type, changes, brief):
    """Send email alert when changes are detected."""
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD or not settings.ALERT_EMAIL:
        logger.info("Email not configured — skipping alert")
        return

    subject = f"🎯 CompetitorRadar: {competitor_name} changed their {page_type}"

    # Build HTML email
    threat = brief.get("threat_level", "UNKNOWN")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a1a;color:#e2e8f0;padding:30px;border-radius:12px;">
        <div style="text-align:center;margin-bottom:20px;">
            <span style="font-size:24px;">🎯</span>
            <h1 style="color:#6366f1;margin:5px 0;font-size:20px;">CompetitorRadar Alert</h1>
        </div>

        <div style="background:rgba(255,255,255,0.05);padding:16px;border-radius:8px;border-left:4px solid #6366f1;margin-bottom:16px;">
            <h2 style="margin:0 0 8px;color:#fff;font-size:16px;">{competitor_name} — {page_type}</h2>
            <p style="margin:0;color:#94a3b8;font-size:13px;">Changes detected during auto-scan</p>
        </div>

        <div style="margin-bottom:16px;">
            <h3 style="color:#6366f1;font-size:12px;letter-spacing:1px;">WHAT CHANGED</h3>
            <p style="color:#cbd5e1;font-size:14px;line-height:1.6;">{brief.get('what_changed', 'See dashboard for details')}</p>
        </div>

        <div style="margin-bottom:16px;">
            <h3 style="color:#f59e0b;font-size:12px;letter-spacing:1px;">WHY IT MATTERS</h3>
            <p style="color:#cbd5e1;font-size:14px;line-height:1.6;">{brief.get('why_it_matters', 'AI analysis pending')}</p>
        </div>

        <div style="margin-bottom:16px;">
            <h3 style="color:#10b981;font-size:12px;letter-spacing:1px;">WHAT YOU SHOULD DO</h3>
            <p style="color:#cbd5e1;font-size:14px;line-height:1.6;white-space:pre-line;">{brief.get('what_to_do', 'Check dashboard')}</p>
        </div>

        <div style="background:rgba(239,68,68,0.1);padding:12px;border-radius:8px;margin-bottom:16px;">
            <h3 style="color:#ef4444;font-size:12px;letter-spacing:1px;margin:0 0 4px;">THREAT LEVEL</h3>
            <p style="color:#fca5a5;font-size:14px;margin:0;">{threat}</p>
        </div>

        <div style="text-align:center;margin-top:20px;">
            <a href="https://competitor-radar-frontend.vercel.app" style="background:#6366f1;color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;">View Full Report</a>
        </div>

        <p style="text-align:center;color:#475569;font-size:11px;margin-top:20px;">CompetitorRadar AI — Automated Competitive Intelligence</p>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_EMAIL
        msg["To"] = settings.ALERT_EMAIL
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_EMAIL, settings.ALERT_EMAIL, msg.as_string())

        logger.info(f"Email alert sent: {competitor_name} / {page_type}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")