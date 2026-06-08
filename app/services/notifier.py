"""Send the daily summary email for filtered job listings."""

import html as html_lib
import logging
import smtplib
from collections import Counter
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.schemas.job import ScoredJob

logger = logging.getLogger(__name__)

_BADGE_STYLE = (
    "padding:2px 8px; border-radius:10px; font-size:11px; "
    "font-weight:600; margin-left:8px;"
)

_SOURCE_COLORS = {
    "arbeitnow": "#10b981",
    "wttj": "#ff6b00",
    "france_travail": "#003189",
    "adzuna": "#e63329",
    "private": "#64748b",
}

_SOURCE_LABELS = {
    "arbeitnow": "Arbeitnow",
    "wttj": "WTTJ",
    "france_travail": "France Travail",
    "adzuna": "Adzuna",
    "private": "Privé",
}


def _source_badge(source_val: str) -> str:
    color = _SOURCE_COLORS.get(source_val, "#64748b")
    label = _SOURCE_LABELS.get(source_val, source_val)
    return (
        f'<span style="background:{color}; color:white; {_BADGE_STYLE}">'
        f"{label}</span>"
    )


def send_email(jobs: list[ScoredJob], config: dict) -> None:
    """Send the HTML summary email for today's listings.

    Args:
        jobs: list of scored listings to notify (already filtered by min_score).
        config: configuration dict; must contain a "notification" key
            with smtp_server and smtp_port.
    """
    if not jobs:
        logger.info("Aucune offre à notifier, envoi de l'email annulé.")
        return

    notif_cfg = config.get("notification", {})
    smtp_server = notif_cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(notif_cfg.get("smtp_port", 587))

    from_addr = settings.email_address
    to_addr = settings.email_to
    password = settings.email_password

    today = datetime.now().strftime("%d/%m/%Y")
    html = _build_html(jobs, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Jobs du {today} - {len(jobs)} offre(s)"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        logger.info(f"Email envoyé à {to_addr} ({len(jobs)} offres)")
    except Exception as e:
        logger.error(f"Échec de l'envoi de l'email : {e}")
        # Fallback: write to a local HTML file
        fallback_path = f"summary_{datetime.now().strftime('%Y%m%d')}.html"
        with open(fallback_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Résumé écrit dans {fallback_path} en fallback")


def _job_card(job: ScoredJob) -> str:
    """Generate the HTML for a single job card."""
    score = job.relevance_score
    score_color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
    badge = _source_badge(job.source.value)

    posted_at = job.posted_at or ""
    try:
        posted_date = datetime.fromisoformat(posted_at).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        posted_date = ""

    date_part = f" &middot; {posted_date}" if posted_date else ""

    pros_html = "".join(f"<li>{html_lib.escape(p)}</li>" for p in (job.ai_pros or []))
    cons_html = "".join(f"<li>{html_lib.escape(p)}</li>" for p in (job.ai_cons or []))

    ul_style = 'style="margin:4px 0; padding-left:16px;"'
    pros_block = (
        f"<div><strong style='color:#22c55e;'>+</strong>"
        f"<ul {ul_style}>{pros_html}</ul></div>"
        if pros_html
        else ""
    )
    cons_block = (
        f"<div><strong style='color:#ef4444;'>-</strong>"
        f"<ul {ul_style}>{cons_html}</ul></div>"
        if cons_html
        else ""
    )

    safe_url = html_lib.escape(job.url or "#", quote=True)
    safe_title = html_lib.escape(job.title or "N/A")
    safe_company = html_lib.escape(job.company or "N/A")
    safe_location = html_lib.escape(job.location or "N/A")
    safe_summary = html_lib.escape(job.ai_summary or "")

    title_link = (
        f'<a href="{safe_url}" style="color:#2563eb; text-decoration:none;">'
        f"{safe_title}</a>"
    )
    score_badge = (
        f'<span style="background:{score_color}; color:white; padding:4px 12px; '
        f'border-radius:20px; font-weight:bold; font-size:14px;">{score}/100</span>'
    )
    meta = f"{safe_company} &middot; {safe_location}{date_part}"

    return (
        '<div style="border:1px solid #e2e8f0; border-radius:12px; '
        'padding:20px; margin-bottom:16px; background:#fff;">'
        '<div style="display:flex; justify-content:space-between; '
        'align-items:center; margin-bottom:8px;">'
        f'<h2 style="margin:0; font-size:18px; color:#1a202c;">'
        f"{title_link}{badge}</h2>"
        f"{score_badge}"
        "</div>"
        f'<p style="margin:4px 0; color:#64748b; font-size:14px;">{meta}</p>'
        f'<p style="margin:12px 0 8px; color:#334155; font-size:14px; '
        f'line-height:1.5;">{safe_summary}</p>'
        f'<div style="display:flex; gap:20px; font-size:13px;">'
        f"{pros_block}{cons_block}</div>"
        "</div>"
    )


def _build_html(jobs: list[ScoredJob], today: str) -> str:
    """Build the HTML body for the summary email.

    Args:
        jobs: list of scored listings.
        today: today's date in DD/MM/YYYY format.

    Returns:
        Complete HTML string.
    """
    job_cards = "".join(_job_card(j) for j in jobs)

    # Per-source counts for the subtitle
    source_counts = Counter(job.source.value for job in jobs)
    source_summary = " / ".join(
        f"{count} {src}" for src, count in sorted(source_counts.items())
    )

    body_style = (
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; "
        "background:#f8fafc; padding:20px; margin:0;"
    )
    subtitle = (
        f"{today} &middot; {len(jobs)} offre(s) retenue(s) &middot; {source_summary}"
    )

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        f'<body style="{body_style}">'
        '<div style="max-width:640px; margin:0 auto;">'
        '<div style="text-align:center; margin-bottom:24px;">'
        '<h1 style="color:#1e293b; font-size:24px; margin-bottom:4px;">'
        "Tes offres du jour</h1>"
        f'<p style="color:#94a3b8; font-size:14px;">{subtitle}</p>'
        "</div>"
        f"{job_cards}"
        '<p style="text-align:center; color:#94a3b8; font-size:12px; margin-top:24px;">'
        "jobsift &middot; Scores par IA</p>"
        "</div></body></html>"
    )
