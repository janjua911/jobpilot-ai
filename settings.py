"""
settings.py — Settings Page
CV upload + Job preferences + API keys check
"""
import os
from datetime import datetime
import streamlit as st
from utils.streamlit_helpers import show_notification
from utils.cv_storage import extract_text_from_upload, save_cv_to_firestore


def render(db):
    st.title("⚙️ Settings")

    tab1, tab2, tab3 = st.tabs(["📄 CV Upload", "🎯 Job Preferences", "🔑 API Keys"])

    # ══════════════════════
    #  TAB 1 — CV Upload (UPDATED: Saves to BOTH collections)
    # ══════════════════════
    with tab1:
        st.subheader("Apna CV Upload Karo")
        st.caption("Ek baar upload — agents automatically use karenge")

        # Show current CV status
        if st.session_state.get("cv_uploaded"):
            st.success(f"✅ CV uploaded: {st.session_state.get('cv_filename', 'CV')}")
            st.caption(f"Characters: {len(st.session_state.get('cv_text', ''))}")
            
            # Show where it's saved
            st.info("📁 CV saved to Firebase collections: `users` AND `user_profiles`")
            
            if st.button("🔄 New CV Upload Karo"):
                st.session_state.cv_uploaded = False
                st.rerun()
        else:
            uploaded_file = st.file_uploader(
                "CV upload karo (PDF ya DOCX)",
                type=["pdf", "docx"],
            )

            if uploaded_file:
                with st.spinner("CV read kar raha hoon..."):
                    cv_text = extract_text_from_upload(uploaded_file)

                if cv_text:
                    st.session_state.cv_text     = cv_text
                    st.session_state.cv_uploaded = True
                    st.session_state.cv_filename = uploaded_file.name
                    st.session_state.user_id     = "user_001"  # MVP: single user

                    if db:
                        # ✅ Save to users collection (existing)
                        user_ref = db.collection("users").document(st.session_state.user_id)
                        user_ref.set({
                            "cv_text": cv_text,
                            "cv_filename": uploaded_file.name,
                            "cv_updated_at": datetime.utcnow().isoformat(),
                            "cv_length": len(cv_text),
                        }, merge=True)
                        
                        # ✅ ALSO save to user_profiles for agent compatibility
                        profile_ref = db.collection("user_profiles").document(st.session_state.user_id)
                        profile_ref.set({
                            "cv_text": cv_text,
                            "name": st.session_state.get("user_name", "Hassan Afzal"),
                            "cv_filename": uploaded_file.name,
                            "uploaded_at": datetime.utcnow().isoformat(),
                            "cv_length": len(cv_text),
                        }, merge=True)
                        
                        st.success("✅ CV saved to BOTH collections (users + user_profiles)!")
                        st.info("🤖 Agent can now detect your CV in the next cycle.")
                    else:
                        st.warning("⚠️ CV saved to session only (Firebase not connected)")

                    with st.expander("CV Preview"):
                        st.text(cv_text[:800] + ("..." if len(cv_text) > 800 else ""))

                    st.rerun()
                else:
                    st.error("CV read nahi ho saka — dobara try karo")

    # ══════════════════════════
    #  TAB 2 — Job Preferences
    # ══════════════════════════
    with tab2:
        st.subheader("Job Preferences")
        st.caption("Scout Agent in preferences ke mutabiq jobs dhundega")

        col1, col2 = st.columns(2)

        with col1:
            target_roles = st.multiselect(
                "Target Roles",
                options=[
                    "Machine Learning Engineer",
                    "AI Engineer",
                    "Data Scientist",
                    "Software Engineer",
                    "Backend Developer",
                    "Full Stack Developer",
                    "Data Analyst",
                    "Research Intern",
                    "Python Developer",
                ],
                default=st.session_state.get("target_roles", ["Machine Learning Engineer"]),
            )

            locations = st.multiselect(
                "Preferred Locations",
                options=["Islamabad", "Lahore", "Karachi", "Rawalpindi", "Remote", "USA Remote", "UK Remote"],
                default=st.session_state.get("locations", ["Islamabad", "Remote"]),
            )

        with col2:
            work_type = st.multiselect(
                "Work Type",
                options=["Full-time", "Part-time", "Internship", "Contract", "Remote"],
                default=st.session_state.get("work_type", ["Internship", "Remote"]),
            )

            min_match = st.slider(
                "Minimum Match Score (%)",
                min_value=40, max_value=90,
                value=st.session_state.get("min_match_score", 60),
                step=5,
            )

            daily_limit = st.slider(
                "Max Applications Per Day",
                min_value=1, max_value=20,
                value=st.session_state.get("daily_app_limit", 10),
            )

        if st.button("💾 Save Preferences", type="primary"):
            st.session_state.target_roles    = target_roles
            st.session_state.locations       = locations
            st.session_state.work_type       = work_type
            st.session_state.min_match_score = min_match
            st.session_state.daily_app_limit = daily_limit

            # Firebase mein save (both collections)
            if db and st.session_state.get("user_id"):
                try:
                    # Save to users collection
                    db.collection("users").document(
                        st.session_state.user_id
                    ).set({
                        "preferences": {
                            "target_roles": target_roles,
                            "locations":    locations,
                            "work_type":    work_type,
                            "min_match":    min_match,
                            "daily_limit":  daily_limit,
                        },
                        "updated_at": datetime.utcnow().isoformat()
                    }, merge=True)
                    
                    # Also save to user_profiles for agent
                    db.collection("user_profiles").document(
                        st.session_state.user_id
                    ).set({
                        "target_roles": target_roles,
                        "locations": locations,
                        "work_type": work_type,
                        "updated_at": datetime.utcnow().isoformat()
                    }, merge=True)
                    
                except Exception as e:
                    st.warning(f"Firebase save error: {e}")

            show_notification("✅ Preferences save ho gayi!", "success")
            st.rerun()

    # ══════════════════════
    #  TAB 3 — API Keys
    # ══════════════════════
    with tab3:
        st.subheader("API Keys Status")
        st.caption("Yeh sab .env mein honi chahiye")

        required_keys = {
            "GEMINI_API_KEY":   "Gemini AI (LLM)",
            "TINYFISH_API_KEY": "TinyFish (Job Scraping)",
        }
        optional_keys = {
            "GMAIL_ADDRESS":     "Gmail Address",
            "GMAIL_APP_PASSWORD":"Gmail App Password",
            "TELEGRAM_BOT_TOKEN":"Telegram Bot",
            "GROQ_API_KEY":      "Groq API (faster alternative)",
        }

        st.caption("**Required (abhi chahiye)**")
        for env_key, label in required_keys.items():
            val = os.getenv(env_key, "")
            if val and "your_" not in val:
                st.success(f"✅ {label}")
            else:
                st.error(f"❌ {label} — .env mein add karo")

        st.caption("**Optional**")
        for env_key, label in optional_keys.items():
            val = os.getenv(env_key, "")
            if val and "your_" not in val:
                st.success(f"✅ {label}")
            else:
                st.warning(f"⏳ {label} — optional, add for more features")

        st.divider()
        
        # Firebase Connection Status
        col1, col2 = st.columns(2)
        with col1:
            if db:
                st.success("✅ Firebase Firestore — Connected")
            else:
                st.error("❌ Firebase — Check credentials")
        
        with col2:
            # Show where CV is stored
            if st.session_state.get("cv_uploaded"):
                st.info("📄 CV Status: Uploaded & Saved to Both Collections")
            else:
                st.warning("📄 CV Status: Not Uploaded Yet")
