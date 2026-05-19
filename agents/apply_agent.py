"""
agents/apply_agent.py — Email Application Agent
================================================
Sends job applications via Gmail SMTP
Fallback: When no email, send a direct apply link (apply_url) via Telegram.
"""

import os
import smtplib
import logging
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# COMPANY EMAIL DATABASE (unchanged)
# ─────────────────────────────────────────────────────────────
COMPANY_EMAILS = {
    # Tech Giants
    "google": "careers@google.com",
    "microsoft": "careers@microsoft.com",
    "amazon": "jobs@amazon.com",
    "apple": "jobs@apple.com",
    "meta": "careers@meta.com",
    "facebook": "careers@meta.com",
    "netflix": "jobs@netflix.com",

    # Pakistani Companies
    "flatgigs": "careers@flatgigs.com",
    "mercory": "hr@mercory.com",
    "thinkbox co": "jobs@thinkbox.com",
    "thinkbox": "jobs@thinkbox.com",
    "devsinc": "careers@devsinc.com",
    "arbisoft": "jobs@arbisoft.com",
    "venture drive": "hiring@venturedrive.com",
    "systems limited": "careers@systems.com.pk",
    "10pearls": "careers@10pearls.com",
    "confiz": "jobs@confiz.com",

    # International
    "stripe": "jobs@stripe.com",
    "openai": "careers@openai.com",
    "anthropic": "jobs@anthropic.com",
    "databricks": "recruiting@databricks.com",
    "snowflake": "careers@snowflake.com",
    "airbnb": "jobs@airbnb.com",
    "uber": "jobs@uber.com",
    "lyft": "careers@lyft.com",
    "spotify": "jobs@spotify.com",
    "twitter": "careers@twitter.com",
    "linkedin": "jobs@linkedin.com",
    "salesforce": "careers@salesforce.com",
    "oracle": "jobs@oracle.com",
    "ibm": "careers@ibm.com",
    "adobe": "jobs@adobe.com",
    "nvidia": "careers@nvidia.com",
    "intel": "jobs@intel.com",
    "amd": "careers@amd.com",
    "qualcomm": "jobs@qualcomm.com",

    # Remote/Startups
    "remote": "jobs@remote.com",
    "gitlab": "jobs@gitlab.com",
    "vercel": "careers@vercel.com",
    "netlify": "jobs@netlify.com",
    "hashicorp": "careers@hashicorp.com",
    "digitalocean": "jobs@digitalocean.com",
    "cloudflare": "careers@cloudflare.com",
    "mongodb": "careers@mongodb.com",
    "elastic": "jobs@elastic.co",
    "reddit": "careers@reddit.com",
    "discord": "jobs@discord.com",
    "slack": "careers@slack.com",
    "zoom": "jobs@zoom.us",
    "dropbox": "careers@dropbox.com",
    "asana": "jobs@asana.com",
    "notion": "careers@notion.so",
    "figma": "jobs@figma.com",
    "canva": "careers@canva.com",
}

EMAIL_PATTERNS = ["careers", "jobs", "hr", "hiring", "recruiting", "talent"]


# ─────────────────────────────────────────────────────────────
# TELEGRAM HELPER (with inline keyboard support)
# ─────────────────────────────────────────────────────────────
def send_telegram_message(text: str, parse_mode: str = "HTML", reply_markup: dict = None) -> bool:
    """Send a message to Hassan on Telegram, optionally with inline buttons."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        logger.warning("Telegram not configured — cannot send message")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message sent successfully")
        return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def send_manual_apply_telegram(
    company: str,
    job_title: str,
    apply_url: str,
    cover_letter: str,
    match_score: int = 0,
) -> bool:
    """
    Send 'Manual Apply Needed' card to Telegram (fallback when no email AND no apply_url).
    Cover letter is split into two messages if long.
    """
    score_bar = "🟢" if match_score >= 75 else "🟡" if match_score >= 55 else "🔴"

    card = (
        f"📋 <b>Manual Apply Needed</b>\n"
        f"{'─' * 32}\n"
        f"🏢 <b>Company:</b> {company}\n"
        f"💼 <b>Role:</b> {job_title}\n"
        f"{score_bar} <b>Match Score:</b> {match_score}%\n\n"
        f"🔗 <b>Apply Here:</b>\n{apply_url}\n\n"
        f"📝 <b>Cover Letter ready</b> — see next message 👇"
    )
    ok1 = send_telegram_message(card)

    MAX_CL = 3800
    if len(cover_letter) > MAX_CL:
        cover_letter_trimmed = cover_letter[:MAX_CL] + "\n\n… <i>(truncated — full version in Firebase)</i>"
    else:
        cover_letter_trimmed = cover_letter

    cl_msg = (
        f"✉️ <b>Cover Letter — {company}</b>\n"
        f"{'─' * 32}\n"
        f"{cover_letter_trimmed}\n\n"
        f"<i>Copy the above and paste when applying ☝️</i>"
    )
    ok2 = send_telegram_message(cl_msg)

    return ok1 and ok2


# ─────────────────────────────────────────────────────────────
# MAIN AGENT
# ─────────────────────────────────────────────────────────────
class ApplyAgent:
    """Send job applications via email, with Telegram fallback using apply_url."""

    def __init__(self):
        self.sender_email = os.getenv("GMAIL_ADDRESS", "")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD", "")

    # ── Public entry point ─────────────────────────────────────
    def apply(
        self,
        job: Dict,
        cover_letter: str,
        cv_bytes: Optional[bytes] = None,
        candidate_name: str = "Hassan Afzal",
    ) -> Dict:
        """
        Smart apply:
          1. Try email (from job data / company DB)
          2. If email found → send via SMTP
          3. Else try to extract apply_url → send Telegram with link + button
          4. Else fallback to old manual instruction (no link)
        Returns a result dict with success, method, message.
        """
        company    = job.get("company", "Unknown Company")
        job_title  = job.get("title", "the position")
        match_score = job.get("match_score", 0)

        # ── 1. Resolve email ───────────────────────────────────
        to_email = get_company_email_from_job(job)

        # ── 2. Try email apply ─────────────────────────────────
        if to_email:
            result = self.send_application(
                to_email=to_email,
                job_title=job_title,
                company_name=company,
                cv_bytes=cv_bytes or b"",
                cover_letter_text=cover_letter,
                candidate_name=candidate_name,
            )
            result["method"] = "email"
            result["to_email"] = to_email
            return result

        # ── 3. No email – try apply_url ─────────────────────────
        apply_url = self._extract_apply_url(job)
        if apply_url:
            return self._notify_url_application(job, cover_letter, apply_url, match_score)

        # ── 4. No email, no URL – old manual message ────────────
        logger.info(f"No email or apply_url for '{company}' — sending old manual instruction")
        tg_ok = send_manual_apply_telegram(
            company=company,
            job_title=job_title,
            apply_url="#",
            cover_letter=cover_letter,
            match_score=match_score,
        )
        if tg_ok:
            return {
                "success": True,   # "handled" so it saves in Firebase
                "method": "telegram_manual_no_link",
                "message": f"📋 No email or link for {company}. Manual instruction sent.",
                "sent_at": datetime.now().isoformat(),
            }
        else:
            return {
                "success": False,
                "method": "none",
                "message": f"❌ No contact method for {company} and Telegram failed.",
                "sent_at": None,
            }

    # ── Helper to extract apply_url from job dict ──────────────
    def _extract_apply_url(self, job: Dict) -> Optional[str]:
        """
        Extract a working application URL from various fields.
        Returns the first valid http(s) URL found.
        """
        candidates = [
            job.get("apply_url"),
            job.get("redirect_url"),
            job.get("url"),
            job.get("application_link"),
            job.get("company_url"),
        ]
        for url in candidates:
            if url and isinstance(url, str) and url.startswith(("http://", "https://")):
                return url

        # Also try to find a link inside the description
        desc = job.get("description", "")
        if desc:
            match = re.search(r'https?://[^\s<>"\'()]+', desc)
            if match:
                return match.group(0)

        return None

    # ── New: Send Telegram with clickable apply_url + button ────
    def _notify_url_application(self, job: Dict, cover_letter: str, apply_url: str, match_score: int) -> Dict:
        """
        Send a Telegram message with a direct application link and an inline button.
        Also saves the application to Firebase (caller must save).
        """
        company = job.get("company", "Unknown")
        title = job.get("title", "Position")

        # Build inline keyboard with one button
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔗 Apply Now", "url": apply_url}]
            ]
        }

        message = (
            f"🔗 <b>Apply using this link</b>\n"
            f"{'─' * 32}\n"
            f"🏢 {company}\n"
            f"💼 {title}\n"
            f"📊 Match: {match_score}%\n\n"
            f"👉 <a href='{apply_url}'>Click here to open application form</a>\n\n"
            f"⚠️ Auto-apply not possible – please complete the application manually.\n"
            f"📝 Cover letter is ready below 👇"
        )

        send_telegram_message(message, reply_markup=keyboard)

        # Send cover letter as a separate message (no button needed)
        MAX_CL = 3800
        if len(cover_letter) > MAX_CL:
            cover_letter = cover_letter[:MAX_CL] + "\n\n… <i>(truncated)</i>"
        cl_msg = (
            f"✉️ <b>Cover Letter — {company}</b>\n"
            f"{'─' * 32}\n"
            f"{cover_letter}\n\n"
            f"<i>Copy and paste when applying ☝️</i>"
        )
        send_telegram_message(cl_msg)

        return {
            "success": True,
            "method": "telegram_link",
            "message": f"🔗 Application link sent to Telegram for {company}",
            "sent_at": datetime.now().isoformat(),
            "apply_url": apply_url,
        }

    # ── Legacy email sending (unchanged) ────────────────────────
    def send_application(
        self,
        to_email: str,
        job_title: str,
        company_name: str,
        cv_bytes: bytes,
        cover_letter_text: str,
        candidate_name: str = "Hassan Afzal",
    ) -> Dict:
        """Send application email with CV attached."""
        if not self.sender_email or not self.app_password:
            return {
                "success": False,
                "message": "❌ Gmail not configured. Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env",
                "sent_at": None,
            }

        if not to_email or "@" not in to_email:
            return {
                "success": False,
                "message": f"⚠️ Invalid email for {company_name}.",
                "sent_at": None,
            }

        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = to_email
            msg["Subject"] = f"Application for {job_title} — {candidate_name}"

            body = self._build_email_body(candidate_name, job_title, company_name, cover_letter_text)
            msg.attach(MIMEText(body, "plain"))

            if cv_bytes:
                filename = f"{candidate_name.replace(' ', '_')}_{job_title.replace(' ', '_')}_CV.docx"
                self._attach_file(msg, cv_bytes, filename)

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender_email, self.app_password)
                server.send_message(msg)

            return {
                "success": True,
                "message": f"✅ Application sent to {company_name} at {to_email}",
                "sent_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Email send error: {e}")
            return {
                "success": False,
                "message": f"❌ Failed to send email: {str(e)[:120]}",
                "sent_at": None,
            }

    def _build_email_body(self, name: str, job_title: str, company: str, cover_letter: str) -> str:
        return f"""Dear Hiring Manager,

{cover_letter}

---
{name}
📧 {self.sender_email}
🔗 github.com/janjua911
🔗 linkedin.com/in/hassanafzal

This application was sent via JobPilot AI
"""

    def _attach_file(self, msg, file_bytes: bytes, filename: str):
        part = MIMEBase(
            "application",
            "vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        part.set_payload(file_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)


# ─────────────────────────────────────────────────────────────
# EMAIL LOOKUP HELPERS (unchanged)
# ─────────────────────────────────────────────────────────────
def get_company_email_from_name(company_name: str) -> Optional[str]:
    if not company_name:
        return None

    company_lower = company_name.lower().strip()

    # Strip common legal suffixes
    for suffix in ["inc", "llc", "ltd", "limited", "corp", "corporation",
                   "co", "company", "technologies", "solutions", "the"]:
        company_lower = re.sub(rf'\b{suffix}\b', "", company_lower).strip()

    company_clean = re.sub(r"[^a-z0-9]", "", company_lower)

    # Direct DB lookup
    for key in [company_name.lower().strip(), company_lower, company_clean]:
        if key in COMPANY_EMAILS:
            return COMPANY_EMAILS[key]

    # Generate educated guess
    if company_clean:
        return f"careers@{company_clean}.com"

    return None


def get_company_email_from_job(job: Dict) -> Optional[str]:
    # 1. Direct field
    for field in ("company_email", "email", "contact_email"):
        val = job.get(field, "")
        if val and "@" in val:
            return val

    # 2. mailto: in apply URL
    apply_url = job.get("url", job.get("apply_url", ""))
    if "mailto:" in apply_url:
        email = apply_url.replace("mailto:", "").split("?")[0].strip()
        if "@" in email:
            return email

    # 3. Company name DB
    company_name = job.get("company", "")
    if company_name:
        return get_company_email_from_name(company_name)

    return None
