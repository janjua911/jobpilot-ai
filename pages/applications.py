"""
pages/applications.py — Applications Tracker (Kanban Board)
===========================================================
Track all applied jobs with status: Applied → Interview → Rejected → Offer
"""

import streamlit as st
from datetime import datetime
import pandas as pd


def show_applications():
    """Display applications kanban board"""
    
    st.markdown("## 📋 Applications Tracker")
    st.markdown("Track your job applications progress")
    
    # Initialize applications in session state
    if "applications" not in st.session_state:
        st.session_state.applications = []
    
    # Load from Firebase if available
    db = st.session_state.get("db")
    if db and not st.session_state.applications:
        _load_applications_from_firebase(db)
    
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    apps = st.session_state.applications
    
    with col1:
        applied = len([a for a in apps if a.get("status") == "applied"])
        st.metric("📤 Applied", applied)
    with col2:
        interviewing = len([a for a in apps if a.get("status") == "interview"])
        st.metric("🎤 Interview", interviewing)
    with col3:
        rejected = len([a for a in apps if a.get("status") == "rejected"])
        st.metric("❌ Rejected", rejected)
    with col4:
        offered = len([a for a in apps if a.get("status") == "offer"])
        st.metric("🎉 Offers", offered)
    
    st.markdown("---")
    
    # ── Kanban Board ───────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    
    statuses = [
        {"name": "📤 Applied", "key": "applied", "color": "blue"},
        {"name": "🎤 Interview", "key": "interview", "color": "orange"},
        {"name": "❌ Rejected", "key": "rejected", "color": "red"},
        {"name": "🎉 Offer", "key": "offer", "color": "green"}
    ]
    
    columns = [col1, col2, col3, col4]
    
    for idx, status in enumerate(statuses):
        with columns[idx]:
            st.markdown(f"### {status['name']}")
            st.markdown("---")
            
            status_apps = [a for a in apps if a.get("status") == status['key']]
            
            if not status_apps:
                st.info("No applications")
            else:
                for app in status_apps:
                    with st.container(border=True):
                        st.markdown(f"**{app.get('title', 'N/A')}**")
                        st.caption(f"🏢 {app.get('company', 'Unknown')}")
                        st.caption(f"📅 Applied: {app.get('applied_date', 'Unknown')}")
                        
                        # Move to next stage button
                        next_status = _get_next_status(status['key'])
                        if next_status:
                            if st.button(f"→ Move to {next_status}", key=f"move_{app['id']}_{idx}"):
                                _update_application_status(app['id'], next_status, db)
                                st.rerun()
                        
                        # View details
                        with st.expander("Details"):
                            st.markdown(f"**Location:** {app.get('location', 'N/A')}")
                            st.markdown(f"**Source:** {app.get('source', 'N/A')}")
                            if app.get("url"):
                                st.markdown(f"[Apply Link]({app.get('url')})")
                            
                            # Notes
                            note = st.text_area(
                                "Notes",
                                value=app.get("notes", ""),
                                key=f"note_{app['id']}",
                                height=68
                            )
                            if note != app.get("notes"):
                                app["notes"] = note
                                if db:
                                    db.collection("applications").document(app['id']).set({
                                        "notes": note
                                    }, merge=True)
    
    st.markdown("---")
    
    # ── Export Option ──
    if st.button("📊 Export Applications to CSV"):
        if apps:
            df = pd.DataFrame(apps)
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"applications_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )


def _load_applications_from_firebase(db):
    """Load applications from Firebase"""
    try:
        docs = db.collection("applications").where("user_id", "==", "user_001").stream()
        apps = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            apps.append(data)
        st.session_state.applications = apps
    except Exception as e:
        st.warning(f"Could not load applications: {e}")


def _update_application_status(app_id: str, new_status: str, db):
    """Update application status in session and Firebase"""
    for app in st.session_state.applications:
        if app.get("id") == app_id:
            app["status"] = new_status
            app["updated_at"] = datetime.now().isoformat()
            break
    
    if db:
        db.collection("applications").document(app_id).set({
            "status": new_status,
            "updated_at": datetime.now().isoformat()
        }, merge=True)


def _get_next_status(current: str) -> str:
    """Get next status in workflow"""
    status_flow = {
        "applied": "interview",
        "interview": "offer",
        "rejected": None,
        "offer": None
    }
    return status_flow.get(current)


def add_application_from_job(job: dict, db):
    """Add a job to applications (called from job feed when user clicks Apply)"""
    
    # Check if already applied
    existing = [a for a in st.session_state.applications if a.get("job_id") == job.get("id")]
    if existing:
        return False, "Already applied"
    
    application = {
        "id": f"app_{job.get('id')}",
        "job_id": job.get("id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "url": job.get("url"),
        "source": job.get("source"),
        "status": "applied",
        "applied_date": datetime.now().strftime("%Y-%m-%d"),
        "updated_at": datetime.now().isoformat(),
        "user_id": "user_001",
        "notes": ""
    }
    
    st.session_state.applications.append(application)
    
    if db:
        db.collection("applications").document(application["id"]).set(application)
    
    return True, "Application tracked!"


# For testing
if __name__ == "__main__":
    show_applications()