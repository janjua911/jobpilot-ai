"""
streamlit_helpers.py — Streamlit Threading Fix
===============================================
Bottleneck #2 Fix: Streamlit Single Thread Problem

Problem:  User A ka Scout Agent chal raha hai (30 sec)
          User B wait karta raha — app "frozen" lagti hai

Fix:
  1. @st.cache_data       → Results cache karo, re-computation avoid karo
  2. @st.cache_resource   → Heavy objects (DB clients) share karo across users
  3. st.session_state     → Per-user state track karo
  4. Background simulation → Long tasks ko status ke saath dikhao

NOTE: Free tier pe true background threads nahi hote Streamlit Share pe.
      Yeh pattern best-effort simulation hai jo UX dramatically improve karta hai.
      True async chahiye toh FastAPI + Celery (Growth Phase mein upgrade).
"""

import time
import logging
from typing import Callable, Any, Optional
from functools import wraps
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  SESSION STATE INITIALIZATION
#  app.py ke top pe ek baar call karo
# ─────────────────────────────────────────────
def init_session_state() -> None:
    """
    Saari session state keys initialize karo.
    app.py mein pehli cheez yahi call karo.
    Streamlit rerun pe existing values preserve hoti hain.
    """
    defaults = {
        # User state
        "user_id":           None,
        "user_profile":      {},
        "cv_uploaded":       False,
        "cv_text":           "",
        
        # Agent task states
        "scout_running":     False,
        "scout_status":      "",
        "scout_progress":    0,
        "scout_results":     [],
        "scout_last_run":    None,
        
        "analyzer_running":  False,
        "analyzer_status":   "",
        "analyzer_progress": 0,
        
        "optimizer_running": False,
        "optimizer_status":  "",
        
        # Data cache (avoid repeated Firebase reads)
        "jobs_cache":        [],
        "jobs_cache_time":   0,
        "apps_cache":        [],
        "apps_cache_time":   0,
        
        # UI state
        "current_page":      "Home",
        "selected_job_id":   None,
        "notification":      None,
    }
    
    for key, default_val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


# ─────────────────────────────────────────────
#  SMART DATA CACHE  (Bottleneck #2 + #4 fix)
# ─────────────────────────────────────────────
CACHE_TTL = {
    "jobs":  300,   # 5 minutes — jobs frequently change
    "apps":  60,    # 1 minute — application status changes fast
    "stats": 600,   # 10 minutes — analytics stable
}

def get_cached_or_fetch(
    cache_key: str,
    fetch_fn: Callable,
    ttl_seconds: int = 300,
    *args,
    **kwargs,
) -> Any:
    """
    Generic session-state cache.
    
    Usage:
        jobs = get_cached_or_fetch(
            "jobs_cache",
            firebase_manager.get_jobs,
            ttl_seconds=300,
            min_score=60
        )
    """
    time_key  = f"{cache_key}_time"
    data_key  = f"{cache_key}_data"
    
    now = time.time()
    cached_time = st.session_state.get(time_key, 0)
    cached_data = st.session_state.get(data_key)
    
    if cached_data is not None and (now - cached_time) < ttl_seconds:
        return cached_data   # Cache hit — no fetch
    
    # Cache miss — fetch fresh data
    fresh_data = fetch_fn(*args, **kwargs)
    st.session_state[data_key] = fresh_data
    st.session_state[time_key] = now
    return fresh_data


# ─────────────────────────────────────────────
#  TASK RUNNER  (Long tasks ke liye UX fix)
# ─────────────────────────────────────────────
class AgentTaskRunner:
    """
    Long-running agent tasks ko Streamlit mein handle karo.
    
    Streamlit threading limitation ke sath:
    - Progress bar show karo (user ko pata chale kuch ho raha hai)
    - Chunked processing karo (zyada responsive feel)
    - Results session mein save karo (rerun pe loss nahi)
    
    Usage:
        runner = AgentTaskRunner("scout")
        
        if st.button("🔍 Find Jobs") and not runner.is_running():
            with runner.run_context("Searching for jobs..."):
                results = scout_agent.run(user_prefs)
                runner.save_results(results)
    """

    def __init__(self, agent_name: str):
        self.agent_name     = agent_name
        self.running_key    = f"{agent_name}_running"
        self.status_key     = f"{agent_name}_status"
        self.progress_key   = f"{agent_name}_progress"
        self.results_key    = f"{agent_name}_results"
        self.last_run_key   = f"{agent_name}_last_run"

    def is_running(self) -> bool:
        return st.session_state.get(self.running_key, False)

    def start(self, status: str = "Starting...") -> None:
        st.session_state[self.running_key]  = True
        st.session_state[self.status_key]   = status
        st.session_state[self.progress_key] = 0

    def update_progress(self, progress: int, status: str) -> None:
        """0-100 progress, status message."""
        st.session_state[self.progress_key] = min(progress, 100)
        st.session_state[self.status_key]   = status

    def finish(self, results: Any = None) -> None:
        st.session_state[self.running_key]  = False
        st.session_state[self.progress_key] = 100
        st.session_state[self.status_key]   = "Done ✅"
        st.session_state[self.last_run_key] = datetime.now().strftime("%H:%M")
        if results is not None:
            st.session_state[self.results_key] = results

    def fail(self, error: str) -> None:
        st.session_state[self.running_key] = False
        st.session_state[self.status_key]  = f"Error: {error}"
        logger.error(f"[{self.agent_name}] Task failed: {error}")

    def save_results(self, results: Any) -> None:
        st.session_state[self.results_key] = results

    def get_results(self) -> Any:
        return st.session_state.get(self.results_key)

    def render_status_ui(self) -> None:
        """Progress bar + status text render karo."""
        if self.is_running():
            progress = st.session_state.get(self.progress_key, 0)
            status   = st.session_state.get(self.status_key, "Running...")
            st.progress(progress / 100, text=status)
        elif st.session_state.get(self.last_run_key):
            st.caption(f"Last run: {st.session_state[self.last_run_key]}")

    def run_with_progress(self, steps: list[tuple[str, Callable]]) -> Optional[Any]:
        """
        Steps list execute karo, har step ke baad progress update karo.
        
        steps format:
            [
                ("Step 1: Fetching jobs...", fetch_jobs_fn),
                ("Step 2: Analyzing matches...", analyze_fn),
                ("Step 3: Saving results...",  save_fn),
            ]
        
        Returns: Last step ka result
        """
        self.start()
        result = None
        total  = len(steps)
        
        try:
            for i, (label, fn) in enumerate(steps):
                progress = int((i / total) * 90)  # 90% tak — last 10% = save
                self.update_progress(progress, label)
                result = fn()
                time.sleep(0.1)   # Brief pause — Streamlit UI update ke liye
            
            self.finish(result)
            return result
        except Exception as e:
            self.fail(str(e))
            raise


# ─────────────────────────────────────────────
#  NOTIFICATION SYSTEM
# ─────────────────────────────────────────────
def show_notification(message: str, type: str = "success") -> None:
    """
    Next rerun pe notification dikhao.
    type: "success" | "error" | "warning" | "info"
    """
    st.session_state.notification = {"message": message, "type": type}


def render_notification() -> None:
    """app.py ke top pe call karo — pending notifications dikhao."""
    notif = st.session_state.get("notification")
    if notif:
        msg  = notif["message"]
        typ  = notif["type"]
        fn_map = {
            "success": st.success,
            "error":   st.error,
            "warning": st.warning,
            "info":    st.info,
        }
        fn_map.get(typ, st.info)(msg)
        st.session_state.notification = None  # Clear after showing


# ─────────────────────────────────────────────
#  RATE LIMIT GUARD  (User-facing)
# ─────────────────────────────────────────────
def check_rate_limit(action: str, max_per_hour: int = 10) -> bool:
    """
    Per-user action rate limiting — Gemini API protect karo.
    
    Usage:
        if check_rate_limit("cv_optimize", max_per_hour=5):
            # Do the action
        else:
            st.warning("Too many requests. Please wait.")
    
    Returns: True agar action allow hai
    """
    counter_key = f"rl_{action}_count"
    window_key  = f"rl_{action}_window"
    
    now = time.time()
    window_start = st.session_state.get(window_key, 0)
    
    # Reset counter agar 1 hour guzar gaya
    if now - window_start > 3600:
        st.session_state[counter_key] = 0
        st.session_state[window_key]  = now
    
    count = st.session_state.get(counter_key, 0)
    
    if count >= max_per_hour:
        wait_min = int((3600 - (now - window_start)) / 60)
        st.warning(f"⏳ Rate limit: {action} — {wait_min} min mein reset ho jayega")
        return False
    
    st.session_state[counter_key] = count + 1
    return True


# ─────────────────────────────────────────────
#  USAGE IN app.py (Example)
# ─────────────────────────────────────────────
"""
Example — app.py mein aise use karo:

import streamlit as st
from utils.streamlit_helpers import (
    init_session_state, render_notification,
    AgentTaskRunner, check_rate_limit, get_cached_or_fetch
)
from utils.firebase_manager import FirebaseManager
from utils.cache_manager import GeminiCacheManager

# ── App entry point ──
def main():
    init_session_state()          # Pehli cheez
    render_notification()         # Pending alerts dikhao
    
    # ── Scout Agent Button ──
    scout_runner = AgentTaskRunner("scout")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        scout_runner.render_status_ui()
    with col2:
        if st.button("🔍 Find Jobs", disabled=scout_runner.is_running()):
            if check_rate_limit("scout_run", max_per_hour=3):
                # Run scout agent with progress
                from agents.scout_agent import ScoutAgent
                agent = ScoutAgent()
                
                scout_runner.run_with_progress([
                    ("🌐 LinkedIn search kar raha hoon...", lambda: agent.search_linkedin()),
                    ("🇵🇰 Rozee.pk check kar raha hoon...", lambda: agent.search_rozee()),
                    ("🔄 Duplicates hata raha hoon...",     lambda: agent.deduplicate()),
                    ("💾 Firebase mein save kar raha hoon...", lambda: agent.save_results()),
                ])
                show_notification("✅ Nayi jobs mil gayi!", "success")
                st.rerun()
    
    # ── Cached job data ──
    fb = FirebaseManager()
    jobs = get_cached_or_fetch(
        "jobs_cache",
        fb.get_jobs,
        ttl_seconds=300,
        min_score=60.0
    )
    st.write(f"Found {len(jobs)} matching jobs")

if __name__ == "__main__":
    main()
"""
