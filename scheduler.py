"""
scheduler.py — Simplified (agent_runner.py handles autonomous work)
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def auto_scout_job():
    """Stub — actual work agent_runner.py karta hai Railway pe"""
    logger.info(f"Manual scout triggered at {datetime.now()}")
    return []


def init_auto_scheduler():
    pass

def get_scheduler():
    return None
