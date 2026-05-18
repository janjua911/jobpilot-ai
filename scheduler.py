# In your main app.py
from scheduler import init_auto_scheduler, get_scheduler, auto_scout_job

# Initialize scheduler on app start
init_auto_scheduler()

# Display scheduler status in UI
scheduler = get_scheduler()
if scheduler.is_running():
    st.success(f"✅ Auto-scout active - Runs daily at {scheduler.schedule_hour:02d}:{scheduler.schedule_minute:02d}")
    status = scheduler.get_status()
    st.info(f"Last run: {status['last_run']}")
else:
    st.info("Auto-scout is disabled")
