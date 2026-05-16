"""
job_feed.py — Job Feed Page
"""
import streamlit as st
from utils.streamlit_helpers import AgentTaskRunner, show_notification, check_rate_limit
import logging

logger = logging.getLogger(__name__)


def render(db):
    st.title("🔍 Job Feed")

    if not st.session_state.get("cv_uploaded"):
        st.warning("⚠️ Pehle CV upload karo — Settings mein jao")
        return

    # Preferences change detect
    current_roles = str(st.session_state.get("target_roles", []))
    last_roles = st.session_state.get("_last_scout_roles", "")
    if current_roles != last_roles and st.session_state.get("jobs_list"):
        st.session_state.jobs_list = []
        st.info("🔄 Preferences badli hain — Jobs Dhundo dabao!")

    runner = AgentTaskRunner("scout")

    # ── Controls ──────────────────────────────
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        runner.render_status_ui()
    
    with col2:
        run_btn = st.button("🔍 Jobs Dhundo", use_container_width=True,
                           type="primary", disabled=runner.is_running())
    
    with col3:
        if st.button("🗑️ Clear", use_container_width=True, disabled=runner.is_running()):
            st.session_state.jobs_list = []
            st.rerun()

    if run_btn:
        if not st.session_state.get("target_roles"):
            st.warning("⚠️ Pehle Job Preferences set karo — Settings mein jao")
        else:
            _run_scout(db, runner)

    st.divider()
    _show_jobs(db)


def _run_scout(db, runner):
    from agents.scout_agent import ScoutAgent, save_jobs_to_firebase
    from agents.analyzer_agent import AnalyzerAgent

    roles = st.session_state.get("target_roles", ["Machine Learning Engineer"])
    locations = st.session_state.get("locations", ["Islamabad", "Remote"])
    work_types = st.session_state.get("work_type", ["Internship", "Full-time"])

    progress_bar = st.progress(0, text="Scout Agent shuru ho raha hai...")
    status_text = st.empty()

    def update(pct, msg):
        progress_bar.progress(pct / 100, text=msg)
        status_text.caption(msg)

    try:
        runner.start()
        agent = ScoutAgent()
        jobs = agent.run(
            roles=roles, locations=locations, work_types=work_types,
            max_per_query=15, progress_callback=update,
        )

        update(70, "✅ Jobs mil gayi! Ab analyze kar raha hoon...")

        # ✅ AUTO-ANALYZE — No button needed
        cv_text = st.session_state.get("cv_text", "")
        if cv_text and jobs:
            analyzer = AnalyzerAgent()
            total = len(jobs)
            
            for i, job in enumerate(jobs):
                # Update progress every 2 jobs
                if i % 2 == 0:
                    update(70 + int((i/total) * 25), f"📊 Analyzing {i+1}/{total}: {job.get('title', 'Job')[:30]}...")
                
                try:
                    analysis = analyzer.analyze_match(
                        cv_text=cv_text,
                        jd_text=job.get("description", "")[:3000],
                        job_title=job.get("title", ""),
                        company_name=job.get("company", "")
                    )
                    job["match_score"] = analysis.get("match_score", 0)
                    job["matched_skills"] = analysis.get("matched_skills", [])
                    job["missing_skills"] = analysis.get("missing_skills", [])
                    job["recommendation"] = analysis.get("recommendation", "")
                    job["quick_analysis"] = analysis.get("quick_analysis", "")
                except Exception as e:
                    logger.warning(f"Analysis failed for {job.get('title')}: {e}")
                    job["match_score"] = 0
                    job["matched_skills"] = []
                    job["missing_skills"] = []
                    job["recommendation"] = "Analysis temporarily unavailable"
                    job["quick_analysis"] = "Analysis error"

        update(95, "💾 Firebase mein save kar raha hoon...")

        # Save to Firebase
        if db:
            # Clear old jobs
            old_docs = db.collection("jobs").limit(500).stream()
            batch = db.batch()
            for d in old_docs:
                batch.delete(d.reference)
            batch.commit()

        saved = save_jobs_to_firebase(db, jobs)

        st.session_state.jobs_list = jobs
        st.session_state.total_jobs = len(jobs)
        st.session_state._last_scout_roles = str(roles)

        runner.finish(jobs)
        progress_bar.progress(100, text=f"✅ {len(jobs)} jobs analyzed!")
        
        # Show summary
        high_matches = len([j for j in jobs if j.get("match_score", 0) >= 70])
        st.success(f"📊 {len(jobs)} jobs mili, {high_matches} high matches (70%+)")
        st.rerun()

    except Exception as e:
        runner.fail(str(e))
        progress_bar.empty()
        st.error(f"❌ Scout Agent error: {e}")


def _send_application_email(job, company_email, db):
    """Helper function to send application email"""
    from agents.apply_agent import ApplyAgent
    from agents.optimizer_agent import OptimizerAgent
    from pages.applications import add_application_from_job
    
    # Get optimized CV if exists, otherwise generate
    optimized = st.session_state.get(f"optimized_cv_{job['id']}")
    
    if not optimized:
        st.info("📄 Generating tailored CV first...")
        optimizer = OptimizerAgent()
        optimized = optimizer.optimize_cv_for_job(
            cv_text=st.session_state.cv_text,
            jd_text=job.get("description", ""),
            job_title=job.get("title", ""),
            company_name=job.get("company", ""),
            candidate_name=st.session_state.get("user_name", "Hassan Afzal")
        )
        st.session_state[f"optimized_cv_{job['id']}"] = optimized
    
    # Send email
    with st.spinner(f"📧 Sending application to {job.get('company')}..."):
        apply_agent = ApplyAgent()
        result = apply_agent.send_application(
            to_email=company_email,
            job_title=job.get("title", ""),
            company_name=job.get("company", ""),
            cv_bytes=optimized["cv_docx"],
            cover_letter_text=optimized.get("cover_letter", ""),
            candidate_name=st.session_state.get("user_name", "Hassan Afzal")
        )
        
        if result["success"]:
            # Add to applications tracker
            success, msg = add_application_from_job(job, db)
            st.success(f"✅ {result['message']}")
            if success:
                st.balloons()
                # Update status to applied
                if db:
                    db.collection("jobs").document(job["id"]).update({"status": "applied"})
                    job["status"] = "applied"
        else:
            st.error(f"❌ {result['message']}")


def _show_jobs(db):
    jobs = st.session_state.get("jobs_list", [])
    
    # ✅ Filter out unwanted sites (bebee.com, linkedin aggregators, etc.)
    unwanted_domains = [
        "bebee.com",           # Paid aggregator site
        "linkedin.com/jobs/view",  # LinkedIn internal (requires login)
        "indeed.com/viewjob",      # Indeed internal
        "glassdoor.com/job-listing", # Glassdoor
        "monster.com/job",          # Monster
        "careerbuilder.com/job"     # CareerBuilder
    ]
    
    original_count = len(jobs)
    filtered_jobs = []
    
    for job in jobs:
        url = job.get("url", "")
        should_skip = False
        
        for domain in unwanted_domains:
            if domain in url:
                should_skip = True
                break
        
        # Also filter by source if needed
        source = job.get("source", "")
        if source in ["Bebee", "bebee"]:
            should_skip = True
        
        if not should_skip:
            filtered_jobs.append(job)
    
    # Show filter stats
    filtered_count = len(filtered_jobs)
    if original_count > filtered_count:
        st.info(f"🔍 Filtered out {original_count - filtered_count} jobs from unwanted sites (bebee.com, etc.)")
    
    if not filtered_jobs:
        st.info("🔍 No jobs found after filtering unwanted sites. Try different search criteria.")
        return
    
    # Use filtered jobs
    jobs = filtered_jobs

    # Stats row
    total_jobs = len(jobs)
    analyzed_jobs = sum(1 for j in jobs if j.get("match_score", 0) > 0)
    avg_score = 0
    if analyzed_jobs > 0:
        avg_score = sum(j.get("match_score", 0) for j in jobs if j.get("match_score", 0) > 0) / analyzed_jobs
    
    col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
    with col_stats1:
        st.metric("Total Jobs", total_jobs)
    with col_stats2:
        st.metric("Analyzed", analyzed_jobs)
    with col_stats3:
        st.metric("Remote Jobs", sum(1 for j in jobs if j.get("is_remote", False)))
    with col_stats4:
        st.metric("Avg Match Score", f"{avg_score:.0f}%" if avg_score > 0 else "N/A")
    
    st.divider()

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        min_score = st.slider("Min Score", 0, 100, 0, 5)
    with col2:
        remote_only = st.checkbox("Remote Only")

    filtered = [
        j for j in jobs
        if j.get("match_score", j.get("quick_score", 0)) >= min_score
        and (not remote_only or j.get("is_remote", False))
    ]

    st.caption(f"{len(filtered)} jobs dikh rahi hain")
    st.divider()

    for job in filtered:
        _job_card(job, db)


def _job_card(job, db):
    # Import required modules
    from agents.optimizer_agent import show_optimizer_ui
    from agents.apply_agent import get_company_email_from_job
    
    # Match score display
    score = job.get("match_score", job.get("quick_score", 0))
    if score >= 70:
        badge = f"🟢 {score}%"
    elif score >= 40:
        badge = f"🟡 {score}%"
    elif score > 0:
        badge = f"🔴 {score}%"
    else:
        badge = "⚪ Analyze"

    with st.container(border=True):
        # Three columns: Title/Company, Match Score, Source/Date/Location
        col1, col2, col3 = st.columns([4, 1, 1.5])

        with col1:
            st.markdown(f"**{job.get('title', 'N/A')}**")
            st.caption(f"🏢 {job.get('company', 'Unknown')}")

        with col2:
            st.markdown(f"**Match**<br>{badge}", unsafe_allow_html=True)
            # Show both scores if available
            if job.get("match_score") and job.get("quick_score"):
                st.caption(f"Quick: {job.get('quick_score')}%")

        with col3:
            # ✅ Source with icon
            source = job.get('source', 'Unknown')
            source_icon = {
                'JSearch': '🔍 LinkedIn/Indeed',
                'Adzuna': '📊 Adzuna',
                'RemoteOK': '🌐 RemoteOK',
                'Himalayas': '🏔️ Himalayas',
                'Arbeitnow': '💼 Arbeitnow'
            }.get(source, '🔗')
            
            st.markdown(f"**Source:** {source_icon}")
            
            # ✅ Posted date
            posted_date = job.get('posted_date', 'Recent')
            if posted_date and posted_date != 'Recent':
                st.markdown(f"**Posted:** {posted_date}")
            else:
                st.markdown(f"**Posted:** Recently")
            
            # ✅ Location
            location = job.get('location', 'Remote')
            location_lower = (location or "").lower()
            location_icon = "🏠" if "remote" in location_lower else "📍"
            st.markdown(f"{location_icon} **{location}**")
            
            # ✅ Apply link - show only if not from unwanted domain
            url = job.get('url', '')
            if url and url != "#":
                # Check if URL is from a valid domain
                is_unwanted = False
                unwanted_domains = ["bebee.com", "linkedin.com/jobs/view", "indeed.com/viewjob"]
                for domain in unwanted_domains:
                    if domain in url:
                        is_unwanted = True
                        break
                
                if not is_unwanted:
                    st.markdown(f"[🔗 Apply on {source}]({url})")
                else:
                    st.caption("⚠️ Link removed (aggregator site)")

        # Description
        desc = job.get("description", "")
        if desc:
            with st.expander("📋 Description"):
                st.write(desc[:600] + ("..." if len(desc) > 600 else ""))

        # Show recommendation if available
        recommendation = job.get("recommendation", "")
        if recommendation:
            with st.expander("💡 Recommendation"):
                st.info(recommendation)

        # Show matched skills if available
        matched = job.get("matched_skills", [])
        if matched:
            with st.expander(f"✅ Matched Skills ({len(matched)})"):
                cols = st.columns(3)
                for i, skill in enumerate(matched[:9]):
                    cols[i % 3].markdown(f"`{skill}`")
                if len(matched) > 9:
                    st.caption(f"... and {len(matched) - 9} more")

        # Show missing skills
        missing = job.get("missing_skills", [])
        if missing:
            with st.expander(f"📚 Missing Skills ({len(missing)})"):
                for skill in missing[:5]:
                    st.caption(f"• {skill}")

        # Status dropdown
        status = job.get("status", "new")
        new_status = st.selectbox(
            "Status",
            options=["new", "saved", "applied", "interview", "rejected"],
            index=["new", "saved", "applied", "interview", "rejected"].index(
                status if status in ["new","saved","applied","interview","rejected"] else "new"
            ),
            key=f"status_{job['id']}",
            label_visibility="collapsed",
        )
        if new_status != status and db:
            db.collection("jobs").document(job["id"]).update({"status": new_status})
            job["status"] = new_status
            st.toast(f"✅ Status: {new_status}")
        
        # ✅ Apply buttons section
        st.markdown("---")
        st.markdown("### 📤 Apply for this Job")
        
        col_apply1, col_apply2 = st.columns(2)
        
        with col_apply1:
            if st.button("📧 Apply via Email", key=f"email_apply_{job['id']}"):
                # Check if CV is uploaded
                if not st.session_state.get("cv_text"):
                    st.warning("⚠️ Pehle CV upload karo — Settings mein jao")
                else:
                    # ✅ Get company email
                    company_email = get_company_email_from_job(job)
                    
                    if company_email:
                        # Email found, proceed
                        _send_application_email(job, company_email, db)
                    else:
                        # No email found, ask user with suggestion
                        suggested_email = f"careers@{job.get('company', '').lower().replace(' ', '')}.com"
                        st.info(f"💡 Suggested email: {suggested_email}")
                        
                        manual_email = st.text_input(
                            "Or enter email manually:", 
                            key=f"manual_email_{job['id']}",
                            placeholder="hr@company.com"
                        )
                        
                        col_send, col_cancel = st.columns(2)
                        with col_send:
                            if manual_email and "@" in manual_email:
                                if st.button("📧 Send", key=f"send_manual_{job['id']}"):
                                    _send_application_email(job, manual_email, db)
                        with col_cancel:
                            st.caption("Or use website link to apply")
        
        with col_apply2:
            # Only show website apply button if URL is from a valid domain
            url = job.get("url", "")
            if url and url != "#":
                is_unwanted = False
                unwanted_domains = ["bebee.com", "linkedin.com/jobs/view", "indeed.com/viewjob"]
                for domain in unwanted_domains:
                    if domain in url:
                        is_unwanted = True
                        break
                
                if not is_unwanted:
                    st.link_button("🔗 Apply on Website", url, use_container_width=True)
                else:
                    st.caption("⚠️ Direct link not available (aggregator site)")
        
        # ✅ Optimizer UI button - CV optimizer for this specific job
        show_optimizer_ui(job, db)