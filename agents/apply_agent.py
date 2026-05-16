"""
agents/apply_agent.py — Email Application Agent
================================================
Sends job applications via Gmail SMTP
"""

import os
import smtplib
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# COMPANY EMAIL DATABASE (Add more as you discover)
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

# Add common email patterns
EMAIL_PATTERNS = [
    "careers",
    "jobs",
    "hr",
    "hiring",
    "recruiting",
    "talent",
    "join",
    "work"
]


class ApplyAgent:
    """Send job applications via email"""
    
    def __init__(self):
        self.sender_email = os.getenv("GMAIL_ADDRESS", "")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD", "")
        
    def send_application(
        self,
        to_email: str,
        job_title: str,
        company_name: str,
        cv_bytes: bytes,
        cover_letter_text: str,
        candidate_name: str = "Hassan Afzal"
    ) -> Dict:
        """
        Send application email with CV attached
        """
        
        # Check email configuration
        if not self.sender_email or not self.app_password:
            return {
                "success": False,
                "message": "❌ Gmail not configured. Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env",
                "sent_at": None
            }
        
        # Check if we have valid recipient email
        if not to_email or "@" not in to_email:
            return {
                "success": False,
                "message": f"⚠️ No email found for {company_name}. Please apply manually using the website link.",
                "sent_at": None,
                "suggested_email": get_company_email_from_name(company_name)  # Return suggestion
            }
        
        try:
            # Create email
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = f"Application for {job_title} position - {candidate_name}"
            
            # Email body
            body = self._build_email_body(candidate_name, job_title, company_name, cover_letter_text)
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach CV
            filename = f"{candidate_name}_{job_title.replace(' ', '_')}_CV.docx"
            self._attach_file(msg, cv_bytes, filename)
            
            # Send email
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender_email, self.app_password)
                server.send_message(msg)
            
            return {
                "success": True,
                "message": f"✅ Application sent to {company_name} at {to_email}",
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return {
                "success": False,
                "message": f"❌ Failed to send: {str(e)[:100]}",
                "sent_at": None
            }
    
    def _build_email_body(self, name: str, job_title: str, company: str, cover_letter: str) -> str:
        """Build professional email body"""
        return f"""Dear Hiring Manager,

{cover_letter}

---
{name}
📧 {self.sender_email}
🔗 github.com/hassanafzal
🔗 linkedin.com/in/hassanafzal

This application was sent via JobPilot AI
"""
    
    def _attach_file(self, msg, file_bytes: bytes, filename: str):
        """Attach file to email"""
        part = MIMEBase('application', 'vnd.openxmlformats-officedocument.wordprocessingml.document')
        part.set_payload(file_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part)


def get_company_email_from_name(company_name: str) -> Optional[str]:
    """
    Get company email from database or generate pattern
    """
    if not company_name:
        return None
    
    company_lower = company_name.lower().strip()
    
    # Remove common suffixes
    suffixes = ["inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "technologies", "solutions"]
    company_clean = company_lower
    for suffix in suffixes:
        company_clean = company_clean.replace(suffix, "").strip()
    
    # Remove special characters
    company_clean = re.sub(r'[^a-z0-9]', '', company_clean)
    
    # Direct match in database
    if company_lower in COMPANY_EMAILS:
        return COMPANY_EMAILS[company_lower]
    
    # Try without "the" prefix
    if company_lower.startswith("the "):
        without_the = company_lower[4:]
        if without_the in COMPANY_EMAILS:
            return COMPANY_EMAILS[without_the]
    
    # Try clean version
    if company_clean in COMPANY_EMAILS:
        return COMPANY_EMAILS[company_clean]
    
    # Generate suggested email based on patterns
    for pattern in EMAIL_PATTERNS:
        suggested = f"{pattern}@{company_clean}.com"
        return suggested  # Return first suggestion
    
    return None


def get_company_email_from_job(job: Dict) -> Optional[str]:
    """
    Extract company email from job data
    """
    # Try direct email from job
    company_email = job.get("company_email", "")
    if company_email and "@" in company_email:
        return company_email
    
    # Check apply URL for mailto:
    apply_url = job.get("url", "")
    if "mailto:" in apply_url:
        email = apply_url.replace("mailto:", "").split("?")[0]
        if "@" in email:
            return email
    
    # Try from company name database
    company_name = job.get("company", "")
    if company_name:
        return get_company_email_from_name(company_name)
    
    return None