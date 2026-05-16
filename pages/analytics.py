"""
pages/analytics.py — Analytics Dashboard (Simple & Reliable)
"""

import streamlit as st
import pandas as pd
from collections import Counter
from datetime import datetime


def show_analytics():
    """Main analytics dashboard - simple charts using st.bar_chart"""
    
    st.markdown("## 📊 Analytics Dashboard")
    st.markdown("Track your job search performance and identify skill gaps")
    
    # Get data from session state
    jobs = st.session_state.get("jobs_list", [])
    applications = st.session_state.get("applications", [])
    
    # If no data, show message
    if not jobs and not applications:
        st.info("📊 No data yet. Go to Job Feed and search for jobs first!")
        return
    
    # ─────────────────────────────────────────────
    # TOP STATS ROW
    # ─────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_jobs = len(jobs)
    analyzed_jobs = len([j for j in jobs if j.get("match_score", 0) > 0])
    applied_jobs = len(applications)
    interviews = len([a for a in applications if a.get("status") == "interview"])
    offers = len([a for a in applications if a.get("status") == "offer"])
    
    with col1:
        st.metric("📋 Total Jobs", total_jobs)
    with col2:
        st.metric("✅ Analyzed", analyzed_jobs)
    with col3:
        st.metric("📤 Applied", applied_jobs)
    with col4:
        st.metric("🎤 Interviews", interviews)
    with col5:
        st.metric("🎉 Offers", offers)
    
    st.markdown("---")
    
    # ─────────────────────────────────────────────
    # ROW 1: Match Score Distribution (Simple Bar Chart)
    # ─────────────────────────────────────────────
    st.markdown("### 📈 Match Score Distribution")
    
    if jobs:
        scores = [j.get("match_score", 0) for j in jobs if j.get("match_score", 0) > 0]
        
        if scores:
            # Create score buckets
            buckets = {"0-20%": 0, "21-40%": 0, "41-60%": 0, "61-80%": 0, "81-100%": 0}
            for score in scores:
                if score <= 20:
                    buckets["0-20%"] += 1
                elif score <= 40:
                    buckets["21-40%"] += 1
                elif score <= 60:
                    buckets["41-60%"] += 1
                elif score <= 80:
                    buckets["61-80%"] += 1
                else:
                    buckets["81-100%"] += 1
            
            # Display as DataFrame and bar chart
            df_scores = pd.DataFrame(list(buckets.items()), columns=['Match Score Range', 'Number of Jobs'])
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.bar_chart(df_scores.set_index('Match Score Range'))
            with col2:
                st.dataframe(df_scores, use_container_width=True)
            
            # Average score
            avg_score = sum(scores) / len(scores)
            st.caption(f"📊 Average match score: **{avg_score:.0f}%**")
            
            if avg_score < 50:
                st.warning("💡 Tip: Your match scores are low. Focus on acquiring missing skills highlighted below.")
            elif avg_score > 70:
                st.success("🎯 Great! Your CV aligns well with available jobs.")
        else:
            st.info("No analyzed jobs yet. Search for jobs to see match scores.")
    else:
        st.info("No jobs found. Go to Job Feed and search for jobs!")
    
    st.markdown("---")
    
    # ─────────────────────────────────────────────
    # ROW 2: Top Missing Skills
    # ─────────────────────────────────────────────
    st.markdown("### 🔥 Top Missing Skills")
    
    # Collect all missing skills from jobs
    all_missing = []
    for job in jobs:
        missing = job.get("missing_skills", [])
        if missing:
            all_missing.extend(missing)
    
    if all_missing:
        skill_counts = Counter(all_missing)
        top_skills = skill_counts.most_common(10)
        
        if top_skills:
            df_skills = pd.DataFrame(top_skills, columns=['Skill', 'Jobs Requiring This Skill'])
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.bar_chart(df_skills.set_index('Skill'))
            with col2:
                st.dataframe(df_skills, use_container_width=True)
            
            # Top recommendation
            top_skill = top_skills[0][0] if top_skills else None
            top_count = top_skills[0][1] if top_skills else 0
            if top_skill:
                st.info(f"💡 **Priority Learning:** **{top_skill}** appears in {top_count} jobs. Learn this first!")
        else:
            st.info("No missing skills data available")
    else:
        st.success("🎉 No major skill gaps detected! Great CV!")
    
    st.markdown("---")
    
    # ─────────────────────────────────────────────
    # ROW 3: Jobs by Source
    # ─────────────────────────────────────────────
    st.markdown("### 🗂️ Jobs by Source")
    
    if jobs:
        sources = [j.get("source", "Unknown") for j in jobs]
        source_counts = Counter(sources)
        
        if source_counts:
            df_sources = pd.DataFrame(list(source_counts.items()), columns=['Source', 'Count'])
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.bar_chart(df_sources.set_index('Source'))
            with col2:
                st.dataframe(df_sources, use_container_width=True)
    
    st.markdown("---")
    
    # ─────────────────────────────────────────────
    # ROW 4: Application Status
    # ─────────────────────────────────────────────
    st.markdown("### 📋 Application Status")
    
    if applications:
        statuses = [a.get("status", "applied") for a in applications]
        status_counts = Counter(statuses)
        
        if status_counts:
            df_status = pd.DataFrame(list(status_counts.items()), columns=['Status', 'Count'])
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.bar_chart(df_status.set_index('Status'))
            with col2:
                st.dataframe(df_status, use_container_width=True)
            
            # Conversion rates
            applied_count = status_counts.get("applied", 0)
            interview_count = status_counts.get("interview", 0)
            offer_count = status_counts.get("offer", 0)
            
            if applied_count > 0:
                interview_rate = (interview_count / applied_count) * 100
                st.caption(f"📊 Interview rate: **{interview_rate:.1f}%**")
            if interview_count > 0:
                offer_rate = (offer_count / interview_count) * 100
                st.caption(f"🎯 Offer rate (from interviews): **{offer_rate:.1f}%**")
    else:
        st.info("No applications yet. Start applying to jobs!")
    
    st.markdown("---")
    
    # ─────────────────────────────────────────────
    # ROW 5: Learning Roadmap
    # ─────────────────────────────────────────────
    st.markdown("### 🎓 Personalized Learning Roadmap")
    
    if all_missing:
        # Get top 5 missing skills
        top_5_skills = [skill for skill, _ in skill_counts.most_common(5)]
        
        # Free learning resources
        resources = {
            "python": "🐍 Python for Everybody (Coursera) - Free",
            "react": "⚛️ React - FreeCodeCamp (Free)",
            "kubernetes": "☸️ Kubernetes Basics (K8s official docs + YouTube)",
            "docker": "🐳 Docker Mastery (FreeCodeCamp)",
            "aws": "☁️ AWS Cloud Practitioner (AWS Skill Builder - Free)",
            "sql": "📊 SQL for Data Analysis (Mode Analytics - Free)",
            "tensorflow": "🧠 TensorFlow 2.0 Tutorials (TensorFlow.org)",
            "pytorch": "🔥 PyTorch Tutorials (PyTorch.org)",
            "django": "🌿 Django Girls Tutorial (Free)",
            "fastapi": "⚡ FastAPI Tutorial (FastAPI.tiangolo.com)",
            "java": "☕ Java Programming (YouTube - FreeCodeCamp)",
            "javascript": "📜 JavaScript Tutorial (FreeCodeCamp)",
            "git": "📦 Git & GitHub (Atlassian Tutorials - Free)",
            "machine learning": "🤖 ML Specialization (Coursera - Audit Free)",
            "ai": "🧠 AI For Everyone (Coursera - Free Audit)",
        }
        
        for skill in top_5_skills:
            skill_lower = skill.lower()
            resource = resources.get(skill_lower, f"🔍 Search 'Free {skill} course' on YouTube/Coursera")
            
            with st.container(border=True):
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(f"**📚**")
                with col2:
                    st.markdown(f"**{skill.upper()}**")
                    st.caption(resource)
                    st.caption("⏱️ Estimated: 10-15 hours")
        
        st.info("💡 **Pro Tip:** Dedicate 1 hour daily to learn one missing skill. In 2 weeks, you'll be 70% more competitive!")
    else:
        st.success("🎉 No major skill gaps detected! Focus on applying to jobs with 70%+ match scores.")
    
    # ─────────────────────────────────────────────
    # EXPORT OPTION
    # ─────────────────────────────────────────────
    st.markdown("---")
    
    if st.button("📥 Export Analytics Report (CSV)", use_container_width=True):
        # Create report
        report_data = []
        for job in jobs:
            report_data.append({
                "Title": job.get("title", ""),
                "Company": job.get("company", ""),
                "Match Score": job.get("match_score", 0),
                "Matched Skills": ", ".join(job.get("matched_skills", [])[:5]),
                "Missing Skills": ", ".join(job.get("missing_skills", [])[:5]),
                "Source": job.get("source", ""),
                "Applied": "Yes" if any(a.get("job_id") == job.get("id") for a in applications) else "No"
            })
        
        if report_data:
            df = pd.DataFrame(report_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"jobpilot_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("No data to export")


# For testing
if __name__ == "__main__":
    show_analytics()