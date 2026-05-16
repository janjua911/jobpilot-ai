"""
scheduler.py — Auto Job Scheduler
=================================
Runs Scout Agent automatically at scheduled times
"""

import time
import threading
import logging
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Callable

import streamlit as st

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Background scheduler for automatic job fetching
    
    Usage:
        scheduler = JobScheduler()
        scheduler.start_daily(9, 0)  # 9:00 AM daily
        
        # Check status
        if scheduler.is_running():
            st.info("Auto-scout is active")
    """
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_run = None
        self.next_run = None
        self.schedule_hour = 9
        self.schedule_minute = 0
        self.callback = None
        
    def start_daily(self, hour: int = 9, minute: int = 0, callback: Optional[Callable] = None):
        """
        Start daily scheduler at specified time
        """
        self.schedule_hour = hour
        self.schedule_minute = minute
        self.callback = callback
        self.running = True
        
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info(f"Auto-scheduler started: Daily at {hour:02d}:{minute:02d}")
        
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("Auto-scheduler stopped")
        
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            now = datetime.now()
            
            # Calculate next run time
            next_run = datetime.now().replace(
                hour=self.schedule_hour, 
                minute=self.schedule_minute, 
                second=0, 
                microsecond=0
            )
            
            # If today's time has passed, schedule for tomorrow
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            
            self.next_run = next_run
            
            # Calculate sleep time
            sleep_seconds = (next_run - now).total_seconds()
            
            if sleep_seconds > 0:
                time.sleep(min(sleep_seconds, 3600))  # Check every hour max
                
                # Check if it's time to run
                now = datetime.now()
                if now.hour == self.schedule_hour and now.minute >= self.schedule_minute:
                    if self.last_run is None or self.last_run.date() < now.date():
                        self._execute_job()
                        
    def _execute_job(self):
        """Execute the scheduled job"""
        try:
            logger.info(f"Auto-scout running at {datetime.now()}")
            self.last_run = datetime.now()
            
            if self.callback:
                self.callback()
                
            st.session_state["last_auto_scout"] = self.last_run.strftime("%Y-%m-%d %H:%M")
            logger.info("Auto-scout completed successfully")
            
        except Exception as e:
            logger.error(f"Auto-scout failed: {e}")
            
    def is_running(self) -> bool:
        return self.running
        
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "active": self.running,
            "last_run": self.last_run.strftime("%Y-%m-%d %H:%M") if self.last_run else "Never",
            "next_run": self.next_run.strftime("%Y-%m-%d %H:%M") if self.next_run else "Not scheduled",
            "schedule_time": f"{self.schedule_hour:02d}:{self.schedule_minute:02d}"
        }


# Global scheduler instance
_scheduler = None


def get_scheduler():
    """Get or create global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler


def auto_scout_job():
    """Function to run when scheduler triggers"""
    from agents.scout_agent import ScoutAgent
    from agents.analyzer_agent import AnalyzerAgent
    
    # Get preferences from session
    roles = st.session_state.get("target_roles", ["Machine Learning Engineer"])
    locations = st.session_state.get("locations", ["Remote"])
    work_types = st.session_state.get("work_type", ["Full-time"])
    cv_text = st.session_state.get("cv_text", "")
    
    if not roles or not cv_text:
        logger.warning("Auto-scout skipped: Missing preferences or CV")
        return
    
    try:
        # Fetch jobs
        scout = ScoutAgent()
        jobs = scout.run(
            roles=roles,
            locations=locations,
            work_types=work_types,
            max_per_query=15
        )
        
        # Analyze jobs
        analyzer = AnalyzerAgent()
        for job in jobs:
            analysis = analyzer.analyze_match(
                cv_text=cv_text,
                jd_text=job.get("description", "")[:3000],
                job_title=job.get("title", ""),
                company_name=job.get("company", "")
            )
            job["match_score"] = analysis.get("match_score", 0)
            job["matched_skills"] = analysis.get("matched_skills", [])
            job["missing_skills"] = analysis.get("missing_skills", [])
        
        # Save to session
        st.session_state["jobs_list"] = jobs
        st.session_state["total_jobs"] = len(jobs)
        st.session_state["auto_scout_new_jobs"] = len(jobs)
        
        # Send notification (if Telegram configured)
        _send_auto_scout_notification(len(jobs))
        
        logger.info(f"Auto-scout found {len(jobs)} jobs")
        
    except Exception as e:
        logger.error(f"Auto-scout error: {e}")


def _send_auto_scout_notification(job_count: int):
    """Send notification about new jobs"""
    try:
        # Try Telegram if configured
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if telegram_token and telegram_chat_id:
            import requests
            message = f"🤖 JobPilot AI\n\n✅ Auto-scout completed!\n📊 Found {job_count} new jobs\n🔍 Check Job Feed for details"
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            requests.post(url, json={"chat_id": telegram_chat_id, "text": message})
    except:
        pass
