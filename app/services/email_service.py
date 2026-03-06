"""
Email service — change alerts + weekly digest.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_change_alert(competitor_name, page_type, changes, brief):
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD or not settings.ALERT_EMAIL:
        logger.info("Email not configured - skipping alert")
        return
    subject = f"CompetitorRadar: {competitor_name} changed their {page_type}"
    threat = brief.get("threat_level", "UNKNOWN")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a1a;color:#e2e8f0;padding:30px;border-radius:12px;">
        <div style="text-align:center;margin-bottom:20px;">
            <h1 style="color:#6366f1;margin:5px 0;font-size:20px;">CompetitorRadar Alert</h1>
        </div>
        <div style="background:rgba(255,255,255,0.05);padding:16px;border-radius:8px;border-left:4px solid #6366f1;margin-bottom:16px;">
            <h2 style="margin:0 0 8px;color:#fff;font-size:16px;">{competitor_name} - {page_type}</h2>
        </div>
        <div style="margin-bottom:16px;">
            <h3 style="color:#6366f1;font-size:12px;letter-spacing:1px;">WHAT CHANGED</h3>
            <p style="color:#cbd5e1;font-size:14px;">{brief.get('what_changed', 'See dashboard')}</p>
        </div>
        <div style="margin-bottom:16px;">
            <h3 style="color:#f59e0b;font-size:12px;letter-spacing:1px;">WHY IT MATTERS</h3>
            <p style="color:#cbd5e1;font-size:14px;">{brief.get('why_it_matters', '')}</p>
        </div>
        <div style="margin-bottom:16px;">
            <h3 style="color:#10b981;font-size:12px;letter-spacing:1px;">WHAT TO DO</h3>
            <p style="color:#cbd5e1;font-size:14px;white-space:pre-line;">{brief.get('what_to_do', '')}</p>
        </div>
        <div style="background:rgba(239,68,68,0.1);padding:12px;border-radius:8px;margin-bottom:16px;">
            <h3 style="color:#ef4444;font-size:12px;">THREAT LEVEL: {threat}</h3>
        </div>
        <div style="text-align:center;margin-top:20px;">
            <a href="https://competitor-radar-frontend.vercel.app" style="background:#6366f1;color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">View Dashboard</a>
        </div>
    </div>"""
    _send_email(subject, html)


async def send_weekly_digest(changes_by_competitor, total_changes, total_briefs):
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD or not settings.ALERT_EMAIL:
        logger.info("Email not configured - skipping digest")
        return
    
    subject = f"CompetitorRadar Weekly Digest: {total_changes} changes detected"
    
    competitor_rows = ""
    for comp_name, data in changes_by_competitor.items():
        count = data["count"]
        max_sig = data["max_significance"]
        sig_color = "#ef4444" if max_sig >= 0.8 else "#f59e0b" if max_sig >= 0.5 else "#10b981"
        top_change = data["top_change"]
        competitor_rows += f"""
        <div style="background:rgba(255,255,255,0.03);padding:14px;border-radius:8px;margin-bottom:10px;border-left:4px solid {sig_color};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="color:#fff;font-size:15px;font-weight:700;">{comp_name}</div>
                    <div style="color:#94a3b8;font-size:12px;margin-top:4px;">{top_change}</div>
                </div>
                <div style="text-align:right;">
                    <div style="color:{sig_color};font-size:20px;font-weight:800;">{count}</div>
                    <div style="color:#64748b;font-size:10px;">changes</div>
                </div>
            </div>
        </div>"""
    
    high_priority = sum(1 for d in changes_by_competitor.values() if d["max_significance"] >= 0.8)
    
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a1a;color:#e2e8f0;padding:30px;border-radius:12px;">
        <div style="text-align:center;margin-bottom:24px;">
            <h1 style="color:#6366f1;margin:0 0 4px;font-size:22px;">Weekly Intelligence Digest</h1>
            <p style="color:#64748b;font-size:12px;margin:0;">CompetitorRadar - Your weekly competitive summary</p>
        </div>
        
        <div style="display:flex;gap:10px;margin-bottom:24px;">
            <div style="flex:1;background:rgba(99,102,241,0.08);padding:14px;border-radius:8px;text-align:center;">
                <div style="color:#6366f1;font-size:28px;font-weight:800;">{total_changes}</div>
                <div style="color:#64748b;font-size:10px;letter-spacing:1px;">CHANGES</div>
            </div>
            <div style="flex:1;background:rgba(239,68,68,0.08);padding:14px;border-radius:8px;text-align:center;">
                <div style="color:#ef4444;font-size:28px;font-weight:800;">{high_priority}</div>
                <div style="color:#64748b;font-size:10px;letter-spacing:1px;">HIGH PRIORITY</div>
            </div>
            <div style="flex:1;background:rgba(16,185,129,0.08);padding:14px;border-radius:8px;text-align:center;">
                <div style="color:#10b981;font-size:28px;font-weight:800;">{total_briefs}</div>
                <div style="color:#64748b;font-size:10px;letter-spacing:1px;">AI BRIEFS</div>
            </div>
            <div style="flex:1;background:rgba(6,182,212,0.08);padding:14px;border-radius:8px;text-align:center;">
                <div style="color:#06b6d4;font-size:28px;font-weight:800;">{len(changes_by_competitor)}</div>
                <div style="color:#64748b;font-size:10px;letter-spacing:1px;">COMPETITORS</div>
            </div>
        </div>
        
        <h2 style="color:#fff;font-size:16px;margin:0 0 14px;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:8px;">Changes by Competitor</h2>
        {competitor_rows}
        
        <div style="text-align:center;margin-top:24px;">
            <a href="https://competitor-radar-frontend.vercel.app" style="background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;">View Full Dashboard</a>
        </div>
        
        <p style="text-align:center;color:#475569;font-size:11px;margin-top:20px;">CompetitorRadar AI - Automated Competitive Intelligence</p>
    </div>"""
    
    _send_email(subject, html)
    logger.info(f"Weekly digest sent: {total_changes} changes, {len(changes_by_competitor)} competitors")


def _send_email(subject, html):
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
        logger.info(f"Email sent: {subject}")
    except Exception as e:
        logger.error(f"Email failed: {e}")