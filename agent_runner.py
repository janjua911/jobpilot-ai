# agent_runner.py — TUMHARA ASLI AUTONOMOUS AGENT
# Yeh file Railway pe deploy hogi — Streamlit se koi connection nahi

import os
import time
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s — %(message)s')
log = logging.getLogger(__name__)

# ── Telegram Helper ──────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def telegram(msg, buttons=None):
    """Send message to Hassan on Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return
    
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    
    if buttons:
        # Inline buttons — Hassan can approve/reject from phone
        data["reply_markup"] = {
            "inline_keyboard": [[
                {"text": btn["text"], "callback_data": btn["data"]}
                for btn in buttons
            ]]
        }
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ── Firebase Helper ──────────────────────────────────────
def get_firebase_db():
    """Connect to Firebase — data lives here, NOT in st.session_state"""
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id":                 os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id":             os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key":                os.getenv("FIREBASE_PRIVATE_KEY","").replace("\\n","\n"),
            "client_email":               os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id":                  os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri":                   "https://accounts.google.com/o/oauth2/auth",
            "token_uri":                  "https://oauth2.googleapis.com/token",
        })
        firebase_admin.initialize_app(cred)
    return firestore.client()

def get_user_profile(db):
    """Read Hassan's CV + preferences from Firebase (not session state)"""
    try:
        doc = db.collection("user_profile").document("hassan").get()
        if doc.exists:
            return doc.to_dict()
        return {}
    except Exception as e:
        log.error(f"Firebase read error: {e}")
        return {}

def save_job_to_firebase(db, job):
    """Save found job to Firebase"""
    try:
        db.collection("jobs").document(job["id"]).set(job)
    except Exception as e:
        log.error(f"Firebase write error: {e}")

def save_application(db, application):
    """Save sent application to Firebase"""
    try:
        db.collection("applications").add(application)
    except Exception as e:
        log.error(f"Firebase write error: {e}")

# ── Core Agent Loop ──────────────────────────────────────
def run_agent_cycle(db):
    """
    One complete agent cycle:
    1. Fetch new jobs
    2. Analyze match
    3. Auto-apply (high match) OR ask Hassan (medium match)
    """
    log.info("="*50)
    log.info("AGENT CYCLE STARTING")
    log.info("="*50)

    # Step 1 — Get Hassan's profile from Firebase
    profile = get_user_profile(db)
    cv_text = profile.get("cv_text", "")
    roles   = profile.get("target_roles", ["Machine Learning Engineer", "AI Engineer"])
    locs    = profile.get("locations", ["Remote", "Pakistan"])

    if not cv_text:
        log.warning("No CV found in Firebase — skipping cycle")
        telegram("⚠️ JobPilot: CV not found in Firebase. Please upload via dashboard.")
        return

    # Step 2 — Scout: Fetch new jobs
    log.info(f"Scouting jobs for: {roles}")
    from agents.scout_agent import ScoutAgent
    scout = ScoutAgent()
    jobs  = scout.run(roles=roles, locations=locs, max_per_query=10)
    log.info(f"Found {len(jobs)} jobs")

    if not jobs:
        log.info("No new jobs found this cycle")
        return

    # Step 3 — Analyze each job
    from agents.analyzer_agent import AnalyzerAgent
    analyzer = AnalyzerAgent()

    auto_applied  = 0
    needs_approval = []

    for job in jobs:
        jd_text = job.get("description", "")[:3000]
        
        analysis = analyzer.analyze_match(
            cv_text=cv_text,
            jd_text=jd_text,
            job_title=job.get("title",""),
            company_name=job.get("company","")
        )
        
        score = analysis.get("match_score", 0)
        job["match_score"]    = score
        job["missing_skills"] = analysis.get("missing_skills", [])
        job["matched_skills"] = analysis.get("matched_skills", [])
        
        # Save to Firebase regardless
        save_job_to_firebase(db, job)

        log.info(f"  {job['company']} — {job['title']} — Score: {score}%")

        # Step 4 — Decision Engine
        if score >= 75:
            # HIGH MATCH — Auto apply, just notify Hassan
            success = auto_apply(db, job, cv_text, profile)
            if success:
                auto_applied += 1
                telegram(
                    f"✅ <b>AUTO APPLIED</b>\n\n"
                    f"🏢 {job['company']}\n"
                    f"💼 {job['title']}\n"
                    f"📊 Match: {score}%\n"
                    f"🕐 {datetime.now().strftime('%H:%M')}"
                )

        elif score >= 55:
            # MEDIUM MATCH — Ask Hassan first
            needs_approval.append(job)

        else:
            # LOW MATCH — Skip silently
            log.info(f"    Skipped (low match: {score}%)")

    # Step 5 — Ask Hassan about medium-match jobs
    if needs_approval:
        for job in needs_approval[:3]:  # Max 3 per cycle to avoid spam
            telegram(
                f"🤔 <b>APPROVAL NEEDED</b>\n\n"
                f"🏢 {job['company']}\n"
                f"💼 {job['title']}\n"
                f"📊 Match: {job['match_score']}%\n"
                f"❓ Apply karna chahte ho?",
                buttons=[
                    {"text": "✅ Apply Karo",   "data": f"approve_{job['id']}"},
                    {"text": "❌ Skip",          "data": f"skip_{job['id']}"},
                ]
            )

    # Step 6 — Daily Summary
    log.info(f"Cycle complete. Auto-applied: {auto_applied}, Needs approval: {len(needs_approval)}")

def auto_apply(db, job, cv_text, profile):
    """
    Automatically apply to a job:
    1. Tailor CV
    2. Generate cover letter
    3. Send email (if email apply) OR fill form (browser-use — Phase 2)
    """
    try:
        # Tailor CV
        from agents.optimizer_agent import OptimizerAgent
        optimizer = OptimizerAgent()
        result    = optimizer.optimize(
            cv_text=cv_text,
            jd_text=job.get("description","")[:3000],
            job_title=job.get("title",""),
            company_name=job.get("company","")
        )
        tailored_cv    = result.get("tailored_cv", cv_text)
        cover_letter   = result.get("cover_letter", "")

        apply_type = detect_apply_type(job)

        if apply_type == "email":
            from agents.apply_agent import ApplyAgent
            apply_agent = ApplyAgent()
            apply_agent.send_email(
                to_email     = job.get("apply_email"),
                job_title    = job.get("title"),
                company_name = job.get("company"),
                cover_letter = cover_letter,
                cv_text      = tailored_cv,
                name         = profile.get("name", "Hassan Afzal")
            )
        elif apply_type == "form":
            # Phase 2 — browser-use
            log.info(f"Form apply needed — queued for browser agent: {job.get('apply_url')}")
            # browser_agent.fill_and_submit(job.get("apply_url"), profile, tailored_cv)
            # Abhi ke liye — Telegram pe link bhejo
            telegram(
                f"📋 <b>MANUAL NEEDED</b>\n\n"
                f"🏢 {job['company']}\n"
                f"🔗 {job.get('apply_url','No URL')}\n"
                f"CV ready hai — sirf form bharna hai"
            )
            return False

        # Log application to Firebase
        save_application(db, {
            "job_id":      job.get("id"),
            "company":     job.get("company"),
            "title":       job.get("title"),
            "match_score": job.get("match_score"),
            "apply_type":  apply_type,
            "status":      "applied",
            "applied_at":  datetime.now().isoformat(),
            "cv_version":  "tailored",
        })
        return True

    except Exception as e:
        log.error(f"Auto-apply failed for {job.get('company')}: {e}")
        return False

def detect_apply_type(job):
    """Figure out HOW to apply for this job"""
    apply_url   = job.get("apply_url", "")
    description = job.get("description", "").lower()

    # Check for email in description
    import re
    emails = re.findall(r'[\w.]+@[\w.]+\.\w+', description)
    if emails:
        job["apply_email"] = emails[0]
        return "email"

    # Check for Google Form
    if "docs.google.com/forms" in apply_url:
        return "form"

    # Default: try email, fallback to form
    if apply_url:
        return "form"

    return "email"

# ── Telegram Callback Listener ───────────────────────────
def listen_for_approvals(db):
    """
    Listen for Hassan's Yes/No on Telegram
    Runs in a separate thread
    """
    last_update_id = 0
    
    while True:
        try:
            url    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": last_update_id + 1}
            resp   = requests.get(url, params=params, timeout=35)
            data   = resp.json()

            for update in data.get("result", []):
                last_update_id = update["update_id"]
                callback = update.get("callback_query")
                
                if callback:
                    cb_data = callback["data"]
                    
                    if cb_data.startswith("approve_"):
                        job_id = cb_data.replace("approve_", "")
                        handle_approval(db, job_id, approved=True)
                        
                    elif cb_data.startswith("skip_"):
                        job_id = cb_data.replace("skip_", "")
                        handle_approval(db, job_id, approved=False)

        except Exception as e:
            log.error(f"Telegram listener error: {e}")
            time.sleep(5)

def handle_approval(db, job_id, approved):
    """Hassan ne approve ya reject kiya — act accordingly"""
    try:
        job_doc = db.collection("jobs").document(job_id).get()
        if not job_doc.exists:
            return
        
        job     = job_doc.to_dict()
        profile = get_user_profile(db)
        cv_text = profile.get("cv_text", "")
        
        if approved:
            telegram(f"⏳ Applying to {job['company']}...")
            success = auto_apply(db, job, cv_text, profile)
            if success:
                telegram(f"✅ Applied to {job['company']} — {job['title']}")
            else:
                telegram(f"❌ Apply failed for {job['company']} — check logs")
        else:
            telegram(f"⏭️ Skipped {job['company']} — {job['title']}")
            db.collection("jobs").document(job_id).update({"status": "skipped"})
            
    except Exception as e:
        log.error(f"Approval handling error: {e}")

# ── MAIN LOOP ────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🚀 JobPilot Agent Runner Starting...")
    
    # Connect to Firebase
    db = get_firebase_db()
    log.info("✅ Firebase connected")
    
    # Send startup notification
    telegram("🚀 <b>JobPilot AI Started</b>\nAgent 24/7 chal raha hai. Raat ko so jao — main kaam karunga. ✅")
    
    # Start Telegram approval listener in background thread
    import threading
    approval_thread = threading.Thread(
        target=listen_for_approvals,
        args=(db,),
        daemon=True
    )
    approval_thread.start()
    log.info("✅ Telegram listener started")

    # MAIN AUTONOMOUS LOOP
    CYCLE_HOURS = 6  # Har 6 ghante mein check karo

    while True:
        try:
            log.info(f"\n🔄 Starting agent cycle at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            run_agent_cycle(db)
            log.info(f"✅ Cycle complete. Next run in {CYCLE_HOURS} hours.\n")
        except Exception as e:
            log.error(f"Agent cycle error: {e}")
            telegram(f"⚠️ Agent error: {str(e)[:100]}")
        
        # Wait for next cycle
        time.sleep(CYCLE_HOURS * 3600)