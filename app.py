"""
app.py — JobPilot AI Main Entry Point
Premium Black Theme + Navigation
"""
import os
import threading
import time
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="JobPilot AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",  # Sidebar hidden — using top nav
)

from firebase_config import init_firebase
from utils.streamlit_helpers import init_session_state, render_notification

# ── Initialize ────────────────────────────────
init_session_state()

try:
    db = init_firebase()
    st.session_state.firebase_ok = True
except Exception as e:
    db = None
    st.session_state.firebase_ok = False

# ── Initialize Auto-Scheduler State ───────────
if "auto_scout_enabled" not in st.session_state:
    st.session_state.auto_scout_enabled = False
if "last_test_run" not in st.session_state:
    st.session_state.last_test_run = "Not yet"

# ── Simple Test Scheduler (Every Hour) ────────
def test_scheduler():
    """Run every hour for testing"""
    from scheduler import auto_scout_job
    
    while True:
        time.sleep(3600)  # 1 hour
        try:
            if st.session_state.get("auto_scout_enabled", False):
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running auto-scout...")
                auto_scout_job()
                st.session_state["last_test_run"] = datetime.now().strftime("%H:%M:%S")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto-scout completed!")
        except Exception as e:
            print(f"[ERROR] Auto-scout failed: {e}")

# ═══════════════════════════════════════════════════════════════
# 🔧 FIXED: Start test scheduler only if NOT disabled via env var
# ═══════════════════════════════════════════════════════════════
if "scheduler_started" not in st.session_state:
    st.session_state.scheduler_started = True
    # ✅ Only start scheduler if DISABLE_SCHEDULER is NOT set
    if not os.getenv("DISABLE_SCHEDULER"):
        thread = threading.Thread(target=test_scheduler, daemon=True)
        thread.start()
        print("[INFO] Test scheduler started! Will run every hour.")
    else:
        print("[INFO] Test scheduler DISABLED via DISABLE_SCHEDULER env var")

# ── Premium Black CSS ─────────────────────────
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main background - Premium Black */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0f0f1a 100%);
    }
    
    /* Main content area */
    .main {
        background: transparent;
    }
    
    /* Glassmorphism Header */
    .glass-header {
        background: rgba(10, 10, 20, 0.7);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding: 0.8rem 2rem;
        margin-bottom: 2rem;
        border-radius: 0 0 20px 20px;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    
    /* Logo text */
    .logo-text {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    /* Navigation buttons */
    .nav-btn {
        background: transparent;
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 0.5rem 1rem;
        color: #ffffff;
        font-weight: 500;
        transition: all 0.3s ease;
        text-align: center;
    }
    
    .nav-btn:hover {
        background: rgba(102, 126, 234, 0.2);
        border-color: #667eea;
        transform: translateY(-2px);
    }
    
    /* Cards */
    .card {
        background: rgba(20, 20, 35, 0.6);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.08);
        padding: 1.2rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .card:hover {
        border-color: rgba(102, 126, 234, 0.5);
        transform: translateY(-3px);
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    }
    
    /* Headings */
    h1, h2, h3 {
        background: linear-gradient(135deg, #ffffff 0%, #a0a0c0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 600;
    }
    
    /* Metrics */
    .stMetric {
        background: rgba(20, 20, 35, 0.5);
        border-radius: 16px;
        padding: 0.8rem;
        border: 1px solid rgba(255,255,255,0.05);
    }
    
    .stMetric label {
        color: #8888aa !important;
    }
    
    .stMetric value {
        color: #667eea !important;
        font-size: 2rem !important;
    }
    
    /* Buttons */
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 20px rgba(102,126,234,0.4);
    }
    
    /* Success/Info/Warning messages */
    .stAlert {
        background: rgba(20, 20, 35, 0.8) !important;
        border-radius: 12px !important;
        border-left: 4px solid #667eea !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(30, 30, 45, 0.6) !important;
        border-radius: 12px !important;
        color: #ccccff !important;
    }
    
    /* Text */
    p, li, caption {
        color: #c0c0d0 !important;
    }
    
    /* Input fields */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background: rgba(30, 30, 45, 0.8) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        color: white !important;
    }
    
    /* Sidebar (if any) - hide it */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    [data-testid="collapsedControl"] {
        display: none;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(30, 30, 45, 0.6);
        border-radius: 12px;
        padding: 0.5rem 1.5rem;
        color: #8888aa;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ── Navigation State ─────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "Home"

# ── Header Navigation ────────────────────────
st.markdown('<div class="glass-header">', unsafe_allow_html=True)
col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])

with col1:
    st.markdown('<span class="logo-text">🚀 JobPilot AI</span>', unsafe_allow_html=True)
    st.caption("Autonomous Job Application Agent")

# Navigation buttons
with col2:
    if st.button("🏠 Home", use_container_width=True, key="nav_home"):
        st.session_state.page = "Home"
        st.rerun()

with col3:
    if st.button("🔍 Jobs", use_container_width=True, key="nav_jobs"):
        st.session_state.page = "Job Feed"
        st.rerun()

with col4:
    if st.button("📄 CV", use_container_width=True, key="nav_cv"):
        st.session_state.page = "My CV"
        st.rerun()

with col5:
    if st.button("📋 Apps", use_container_width=True, key="nav_apps"):
        st.session_state.page = "Applications"
        st.rerun()

with col6:
    if st.button("📊 Stats", use_container_width=True, key="nav_stats"):
        st.session_state.page = "Analytics"
        st.rerun()

with col7:
    if st.button("⚙️ Settings", use_container_width=True, key="nav_settings"):
        st.session_state.page = "Settings"
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ── Status Indicator ─────────────────────────
col_status1, col_status2 = st.columns([6, 1])
with col_status2:
    if st.session_state.get("firebase_ok"):
        st.success("🟢 Live")
    else:
        st.error("🔴 Offline")

# ── Page Functions ───────────────────────────
def show_home():
    st.markdown("## Welcome to JobPilot AI")
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Jobs Found", st.session_state.get("total_jobs", 0))
    with col2:
        st.metric("Applications", st.session_state.get("total_applied", 0))
    with col3:
        st.metric("Match Avg", f"{st.session_state.get('avg_match', 0)}%")
    with col4:
        st.metric("Interviews", st.session_state.get("interviews", 0))
    
    st.markdown("---")
    
    # Auto-Scout Status on Home
    col_status1, col_status2 = st.columns(2)
    with col_status1:
        if st.session_state.auto_scout_enabled:
            st.success("🤖 Auto-Scout is ENABLED — Running every hour")
            st.caption(f"⏰ Last run: {st.session_state.get('last_test_run', 'Not yet')}")
        else:
            st.info("⏸️ Auto-Scout is DISABLED — Enable in Settings")
    
    st.markdown("---")
    
    if not st.session_state.get("cv_uploaded"):
        st.warning("📄 Pehle Settings mein CV upload karo!")
        if st.button("Go to Settings"):
            st.session_state.page = "Settings"
            st.rerun()
    else:
        st.success("✅ CV uploaded! Go to Job Feed to find jobs.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Find Jobs Now", use_container_width=True):
                st.session_state.page = "Job Feed"
                st.rerun()
        with col2:
            if st.button("📊 View Analytics", use_container_width=True):
                st.session_state.page = "Analytics"
                st.rerun()


def show_job_feed():
    from job_feed import render
    render(db)


def show_cv_page():
    st.title("📄 My CV")
    
    if st.session_state.get("cv_uploaded"):
        st.success("✅ CV uploaded successfully!")
        
        # Show CV preview
        cv_text = st.session_state.get("cv_text", "")
        if cv_text:
            with st.expander("📄 CV Preview"):
                st.text(cv_text[:1000] + ("..." if len(cv_text) > 1000 else ""))
        
        st.divider()
        st.subheader("📤 Update CV")
        uploaded_file = st.file_uploader("Upload new CV (PDF or DOCX)", type=["pdf", "docx"])
        if uploaded_file:
            st.info("CV upload functionality coming soon!")
    else:
        st.warning("⚠️ No CV uploaded. Please go to Settings to upload your CV.")
        if st.button("⚙️ Go to Settings"):
            st.session_state.page = "Settings"
            st.rerun()


def show_applications():
    try:
        from pages.applications import show_applications as show_apps
        show_apps()
    except ImportError:
        st.title("📋 Applications")
        st.info("Applications tracker coming soon...")
        
        # Show placeholder
        applications = st.session_state.get("applications", [])
        if applications:
            st.write(f"Total applications: {len(applications)}")
            for app in applications[-5:]:
                st.caption(f"• {app.get('company')} - {app.get('title')} ({app.get('status', 'applied')})")
        else:
            st.info("No applications yet. Apply to jobs from the Job Feed!")


def show_analytics():
    """Analytics dashboard - stats and insights"""
    try:
        from pages.analytics import show_analytics as show_analytics_page
        show_analytics_page()
    except ImportError:
        # Fallback analytics if page doesn't exist yet
        st.title("📊 Analytics Dashboard")
        st.markdown("---")
        
        # Get data from session state
        jobs = st.session_state.get("jobs_list", [])
        applications = st.session_state.get("applications", [])
        
        # Stats row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Jobs Found", len(jobs))
        with col2:
            st.metric("Applications Sent", len(applications))
        with col3:
            analyzed_jobs = len([j for j in jobs if j.get("match_score", 0) > 0])
            st.metric("Jobs Analyzed", analyzed_jobs)
        with col4:
            avg_score = 0
            if analyzed_jobs > 0:
                avg_score = sum(j.get("match_score", 0) for j in jobs if j.get("match_score", 0) > 0) / analyzed_jobs
            st.metric("Avg Match Score", f"{avg_score:.0f}%")
        
        st.markdown("---")
        
        # Match Score Distribution
        st.subheader("📈 Match Score Distribution")
        if jobs:
            scores = [j.get("match_score", 0) for j in jobs if j.get("match_score", 0) > 0]
            if scores:
                bins = {"0-29": 0, "30-49": 0, "50-69": 0, "70-89": 0, "90-100": 0}
                for s in scores:
                    if s < 30:
                        bins["0-29"] += 1
                    elif s < 50:
                        bins["30-49"] += 1
                    elif s < 70:
                        bins["50-69"] += 1
                    elif s < 90:
                        bins["70-89"] += 1
                    else:
                        bins["90-100"] += 1
                
                chart_data = {"Score Range": list(bins.keys()), "Count": list(bins.values())}
                st.bar_chart(chart_data, x="Score Range", y="Count")
            else:
                st.info("No analyzed jobs yet. Run job search to see match scores!")
        else:
            st.info("No jobs found yet. Go to Job Feed and search for jobs!")
        
        st.markdown("---")
        
        # Top Skills
        st.subheader("🔧 Top Skills from Jobs")
        all_skills = []
        for job in jobs:
            skills = job.get("matched_skills", []) + job.get("missing_skills", [])
            all_skills.extend(skills)
        
        if all_skills:
            from collections import Counter
            skill_counts = Counter(all_skills).most_common(10)
            st.write("Most common skills in your job matches:")
            for skill, count in skill_counts:
                st.progress(min(count / max(skill_counts[0][1], 1), 1.0), text=f"{skill}: {count} jobs")
        else:
            st.info("Run job analysis to see skill insights!")
        
        st.markdown("---")
        
        # Application Status
        st.subheader("📊 Application Status")
        if applications:
            from collections import Counter
            status_counts = Counter([app.get("status", "applied") for app in applications])
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📝 Applied", status_counts.get("applied", 0))
            with col2:
                st.metric("📞 Interview", status_counts.get("interview", 0))
            with col3:
                st.metric("❌ Rejected", status_counts.get("rejected", 0))
            with col4:
                st.metric("✅ Offer", status_counts.get("offer", 0))
        else:
            st.info("No applications yet. Start applying from Job Feed!")


def show_settings():
    from settings import render as settings_render
    settings_render(db)
    
    # Add Auto-Scout controls in Settings page
    st.markdown("---")
    st.markdown("### 🤖 Auto-Scout Settings (Test Mode)")
    st.markdown("Automatically fetch jobs every hour for testing")
    
    col1, col2 = st.columns(2)
    
    with col1:
        enabled = st.toggle(
            "Enable Hourly Auto-Scout",
            value=st.session_state.auto_scout_enabled,
            help="Automatically fetch and analyze jobs every hour (for testing)"
        )
        
        if enabled != st.session_state.auto_scout_enabled:
            st.session_state.auto_scout_enabled = enabled
            
            if enabled:
                st.success("✅ Auto-scout enabled! Jobs will be fetched every hour")
            else:
                st.info("⏸️ Auto-scout disabled")
    
    with col2:
        if st.button("🔄 Run Auto-Scout Now", use_container_width=True):
            from scheduler import auto_scout_job
            with st.spinner("Running auto-scout..."):
                auto_scout_job()
                st.session_state.last_test_run = datetime.now().strftime("%H:%M:%S")
            st.success("✅ Auto-scout complete! Check Job Feed for new jobs.")
            st.rerun()
    
    # Show scheduler status
    st.markdown("---")
    st.markdown("### 📅 Scheduler Status")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.auto_scout_enabled:
            st.metric("Status", "🟢 Active")
            st.caption("Running every hour")
        else:
            st.metric("Status", "⚪ Disabled")
    with col2:
        st.metric("Last Run", st.session_state.get('last_test_run', 'Not yet'))
    
    st.caption("⏰ Test schedule: Runs every hour when enabled")
    st.info("💡 Tip: This is for local testing. For production, use a proper cron job or cloud scheduler.")


# ── Page Routing ─────────────────────────────
page = st.session_state.page

if page == "Home":
    show_home()
elif page == "Job Feed":
    show_job_feed()
elif page == "My CV":
    show_cv_page()
elif page == "Applications":
    show_applications()
elif page == "Analytics":
    show_analytics()
elif page == "Settings":
    show_settings()
