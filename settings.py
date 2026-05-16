"""
settings.py — Settings Page
CV upload + Job preferences + API keys check
"""
import os
import streamlit as st
from utils.streamlit_helpers import show_notification
from utils.cv_storage import extract_text_from_upload, save_cv_to_firestore


def render(db):
    st.title("⚙️ Settings")

    tab1, tab2, tab3 = st.tabs(["📄 CV Upload", "🎯 Job Preferences", "🔑 API Keys"])

    # ══════════════════════
    #  TAB 1 — CV Upload
    # ══════════════════════
    with tab1:
        st.subheader("Apna CV Upload Karo")
        st.caption("Ek baar upload — agents automatically use karenge")

        # Show current CV status
        if st.session_state.get("cv_uploaded"):
            st.success(f"✅ CV uploaded: {st.session_state.get('cv_filename', 'CV')}")
            st.caption(f"Characters: {len(st.session_state.get('cv_text', ''))}")
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

                    # Firestore mein save karo (free — text as string)
                    if db:
                        saved = save_cv_to_firestore(
                            db,
                            st.session_state.user_id,
                            cv_text,
                            uploaded_file.name
                        )
                        if saved:
                            st.success("✅ CV uploaded aur Firebase mein save ho gaya!")
                        else:
                            st.warning("CV session mein save hua, Firebase error")
                    else:
                        st.success("✅ CV session mein save ho gaya!")

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

            # Firebase mein save
            if db and st.session_state.get("user_id"):
                try:
                    db.collection("users").document(
                        st.session_state.user_id
                    ).set({
                        "preferences": {
                            "target_roles": target_roles,
                            "locations":    locations,
                            "work_type":    work_type,
                            "min_match":    min_match,
                            "daily_limit":  daily_limit,
                        }
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

        # Required now
        required_keys = {
            "GEMINI_API_KEY":   "Gemini AI (LLM)",
            "TINYFISH_API_KEY": "TinyFish (Job Scraping)",
        }
        optional_keys = {
            "GMAIL_ADDRESS":     "Gmail Address",
            "GMAIL_APP_PASSWORD":"Gmail App Password",
            "TELEGRAM_BOT_TOKEN":"Telegram Bot",
        }

        st.caption("**Required (abhi chahiye)**")
        for env_key, label in required_keys.items():
            val = os.getenv(env_key, "")
            if val and "your_" not in val:
                st.success(f"✅ {label}")
            else:
                st.error(f"❌ {label} — .env mein add karo")

        st.caption("**Optional (Phase 3 mein add karna)**")
        for env_key, label in optional_keys.items():
            val = os.getenv(env_key, "")
            if val and "your_" not in val:
                st.success(f"✅ {label}")
            else:
                st.warning(f"⏳ {label} — baad mein chahiye hogi")

        st.divider()
        if db:
            st.success("✅ Firebase Firestore — Connected")
        else:
            st.error("❌ Firebase — serviceAccountKey.json check karo")