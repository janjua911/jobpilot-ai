"""
agent_runner.py — JobPilot Autonomous Agent
==========================================
Yeh file Streamlit se BILKUL alag hai.
Railway pe 24/7 chalti hai.
Firebase se data padh'ti hai (session state nahi).
Telegram pe notifications bhejti hai.
"""
 
import os
import time
import logging
import requests
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Logging Setup ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("JobPilot")

# ── Config ────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CYCLE_HOURS      = int(os.getenv("AGENT_CYCLE_HOURS", "6"))
AUTO_APPLY_THRESHOLD  = int(os.getenv("AUTO_APPLY_SCORE", "75"))
ASK_THRESHOLD         = int(os.getenv("ASK_SCORE", "55"))

# Startup pe variables ka status print karo
print("=" * 50)
print("🔧 JOBPILOT AGENT STARTING...")
print(f"   TELEGRAM_TOKEN present: {'YES' if TELEGRAM_TOKEN else 'NO'}")
print(f"   TELEGRAM_CHAT_ID present: {'YES' if TELEGRAM_CHAT_ID else 'NO'}")
print(f"   CYCLE_HOURS: {CYCLE_HOURS}")
print(f"   AUTO_APPLY_THRESHOLD: {AUTO_APPLY_THRESHOLD}")
print(f"   ASK_THRESHOLD: {ASK_THRESHOLD}")
print("=" * 50)

# ── Telegram (with FULL debugging) ────────────────────────────
def send_telegram(text, buttons=None):
    """Hassan ko Telegram pe message bhejo - with full debug output"""
    print(f"\n📨 [DEBUG] send_telegram called")
    print(f"   TELEGRAM_TOKEN: {'[SET]' if TELEGRAM_TOKEN else '[MISSING]'}")
    print(f"   TELEGRAM_CHAT_ID: {'[SET]' if TELEGRAM_CHAT_ID else '[MISSING]'}")
    
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping notification")
        print("❌ TELEGRAM_BOT_TOKEN or CHAT_ID missing")
        return False
    
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML"
    }
    
    if buttons:
        data["reply_markup"] = {
            "inline_keyboard": [
                [{"text": b["text"], "callback_data": b["data"]} for b in buttons]
            ]
        }
    
    print(f"   URL: {url[:50]}...")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"   Text preview: {text[:100]}...")
    
    try:
        r = requests.post(url, json=data, timeout=10)
        print(f"   📡 HTTP Status Code: {r.status_code}")
        print(f"   📡 Response Body: {r.text[:300]}")
        
        if r.status_code == 200:
            print("   ✅ Telegram message sent successfully!")
            return True
        else:
            # Ye important hai — non-200 status pe error log
            log.error(f"Telegram API error {r.status_code}: {r.text}")
            print(f"   ❌ Telegram API returned error {r.status_code}: {r.text}")
            return False
    except requests.exceptions.Timeout:
        print("   ❌ Telegram request TIMEOUT")
        log.error("Telegram request timeout")
        return False
    except Exception as e:
        print(f"   ❌ Telegram exception: {type(e).__name__}: {e}")
        log.error(f"Telegram error: {e}")
        return False

def answer_callback(callback_id, text="✅"):
    """Telegram button click ka response"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=5
        )
        print(f"   [DEBUG] Callback answer sent: {text}")
    except Exception as e:
        print(f"   [DEBUG] Callback answer failed: {e}")

# ── Firebase ──────────────────────────────────────────────────
def get_firebase_db():
    """Firebase se directly connect karo (Streamlit ke bina)"""
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    if firebase_admin._apps:
        return firestore.client()
    
    # Environment variables se credentials lo
    private_key = os.getenv("FIREBASE_PRIVATE_KEY", "")
    if not private_key:
        raise ValueError("FIREBASE_PRIVATE_KEY not set in Railway Variables!")
    
    # \n ko actual newlines mein convert karo
    private_key = private_key.replace("\\n", "\n")
    print("   [DEBUG] Firebase private key loaded, length:", len(private_key))
    
    cred_dict = {
        "type":                        "service_account",
        "project_id":                  os.getenv("FIREBASE_PROJECT_ID"),
        "private_key":                 private_key,
        "client_email":                os.getenv("FIREBASE_CLIENT_EMAIL"),
        "private_key_id":              os.getenv("FIREBASE_PRIVATE_KEY_ID", "key1"),
        "client_id":                   os.getenv("FIREBASE_CLIENT_ID", ""),
        "auth_uri":                    "https://accounts.google.com/o/oauth2/auth",
        "token_uri":                   "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url":        ""
    }
    
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    log.info("✅ Firebase connected")
    return firestore.client()

def get_user_profile(db):
    """Hassan ka CV aur preferences Firebase se padho"""
    try:
        docs = db.collection("user_profiles").limit(1).get()
        for doc in docs:
            profile = doc.to_dict()
            log.info(f"Profile loaded: {profile.get('email', 'unknown')}")
            return profile
        
        # Fallback: session data try karo
        session_doc = db.collection("sessions").document("main").get()
        if session_doc.exists:
            return session_doc.to_dict()
        
        log.warning("No user profile found in Firebase")
        return {}
    except Exception as e:
        log.error(f"Profile fetch error: {e}")
        return {}

def save_job(db, job):
    """Job Firebase mein save karo"""
    try:
        job_id = job.get("id", f"job_{int(time.time())}")
        db.collection("jobs").document(str(job_id)).set(job, merge=True)
    except Exception as e:
        log.error(f"Job save error: {e}")

def save_application(db, application):
    """Application Firebase mein log karo"""
    try:
        db.collection("applications").add({
            **application,
            "applied_at": datetime.now().isoformat(),
            "agent":      "autonomous"
        })
        log.info(f"✅ Application saved: {application.get('company')}")
    except Exception as e:
        log.error(f"Application save error: {e}")

def get_pending_job(db, job_id):
    """Pending approval job Firebase se lo"""
    try:
        doc = db.collection("jobs").document(str(job_id)).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except:
        return None

def mark_job_status(db, job_id, status):
    """Job ka status update karo"""
    try:
        db.collection("jobs").document(str(job_id)).update({
            "status":     status,
            "updated_at": datetime.now().isoformat()
        })
    except Exception as e:
        log.error(f"Status update error: {e}")

# ── Email Apply ───────────────────────────────────────────────
def send_application_email(to_email, job, cover_letter, cv_text, name):
    """Gmail SMTP se application email bhejo"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    gmail_user = os.getenv("GMAIL_ADDRESS", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    
    if not gmail_user or not gmail_pass:
        log.warning("Gmail not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg["From"]    = gmail_user
        msg["To"]      = to_email
        msg["Subject"] = f"Application for {job.get('title')} — {name}"
        
        body = f"""{cover_letter}

---
Candidate: {name}
Applied via: JobPilot AI Agent
"""
        msg.attach(MIMEText(body, "plain"))
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(gmail_user, gmail_pass)
        server.send_message(msg)
        server.close()
        
        log.info(f"📧 Email sent to {to_email}")
        return True
    except Exception as e:
        log.error(f"Email error: {e}")
        return False

def detect_apply_email(job):
    """JD mein email dhundo"""
    description = job.get("description", "") + " " + job.get("apply_url", "")
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', description)
    # Common HR emails filter karo
    for email in emails:
        if not any(x in email.lower() for x in ["example", "test", "noreply"]):
            return email
    return None

# ── Core Agent Functions ──────────────────────────────────────
def scout_jobs(profile):
    """Scout Agent: Nai jobs dhundo"""
    try:
        from agents.scout_agent import ScoutAgent
        
        roles     = profile.get("target_roles", ["Machine Learning Engineer", "AI Engineer", "Python Developer"])
        locations = profile.get("locations", ["Remote", "Pakistan", "Islamabad"])
        
        log.info(f"🔍 Scouting jobs for: {roles}")
        scout = ScoutAgent()
        jobs  = scout.run(
            roles      = roles,
            locations  = locations,
            work_types = profile.get("work_type", ["Full-time", "Internship"]),
            max_per_query = 10
        )
        log.info(f"Found {len(jobs)} jobs")
        return jobs
    except Exception as e:
        log.error(f"Scout error: {e}")
        return []

def analyze_job(job, cv_text):
    """Analyzer Agent: CV vs JD match karo"""
    try:
        from agents.analyzer_agent import AnalyzerAgent
        
        analyzer = AnalyzerAgent()
        result   = analyzer.analyze_match(
            cv_text      = cv_text,
            jd_text      = job.get("description", "")[:3000],
            job_title    = job.get("title", ""),
            company_name = job.get("company", "")
        )
        return result
    except Exception as e:
        log.error(f"Analyzer error: {e}")
        return {"match_score": 0, "matched_skills": [], "missing_skills": []}

def optimize_and_apply(db, job, cv_text, profile):
    """Optimizer + Apply Agent: CV tailor karo aur apply karo"""
    try:
        from agents.optimizer_agent import OptimizerAgent
        
        # CV tailor karo
        optimizer = OptimizerAgent()
        result    = optimizer.optimize(
            cv_text      = cv_text,
            jd_text      = job.get("description", "")[:3000],
            job_title    = job.get("title", ""),
            company_name = job.get("company", "")
        )
        
        cover_letter = result.get("cover_letter", "Please find my application attached.")
        
        # Email detect karo
        apply_email = detect_apply_email(job)
        
        if apply_email:
            success = send_application_email(
                to_email     = apply_email,
                job          = job,
                cover_letter = cover_letter,
                cv_text      = cv_text,
                name         = profile.get("name", "Hassan Afzal")
            )
            apply_method = f"email → {apply_email}"
        else:
            # Email nahi mila — Telegram pe link bhejo
            send_telegram(
                f"📋 <b>Apply karna hai (manual)</b>\n\n"
                f"🏢 {job.get('company')}\n"
                f"💼 {job.get('title')}\n"
                f"🔗 {job.get('apply_url', 'No URL')}\n\n"
                f"CV ready hai — form manually bharo"
            )
            success      = False
            apply_method = "manual_required"
        
        # Application log karo
        save_application(db, {
            "job_id":       job.get("id"),
            "company":      job.get("company"),
            "title":        job.get("title"),
            "match_score":  job.get("match_score", 0),
            "apply_method": apply_method,
            "status":       "applied" if success else "manual_required",
            "cover_letter": cover_letter[:500]
        })
        
        return success
        
    except Exception as e:
        log.error(f"Optimizer/Apply error: {e}")
        return False

# ── Main Agent Cycle ──────────────────────────────────────────
def run_agent_cycle(db):
    """Ek complete autonomous cycle"""
    log.info("=" * 50)
    log.info(f"🔄 AGENT CYCLE STARTING — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 50)
    
    # Step 1: Profile padho
    profile = get_user_profile(db)
    cv_text = profile.get("cv_text", "")
    
    if not cv_text:
        log.warning("No CV found — skipping cycle")
        send_telegram(
            "⚠️ <b>JobPilot Alert</b>\n\n"
            "CV Firebase mein nahi mili!\n"
            "App → Settings → CV upload karo"
        )
        return
    
    # Step 2: Jobs dhundo
    jobs = scout_jobs(profile)
    if not jobs:
        log.info("No new jobs found this cycle")
        return
    
    # Step 3: Har job analyze karo
    auto_applied   = 0
    needs_approval = []
    low_match      = 0
    
    for job in jobs:
        # Firebase mein check — already processed?
        existing = db.collection("jobs").document(str(job.get("id", ""))).get()
        if existing.exists and existing.to_dict().get("status"):
            log.info(f"  Already processed: {job.get('company')} — skipping")
            continue
        
        analysis = analyze_job(job, cv_text)
        score    = analysis.get("match_score", 0)
        
        job["match_score"]    = score
        job["matched_skills"] = analysis.get("matched_skills", [])
        job["missing_skills"] = analysis.get("missing_skills", [])
        job["status"]         = "analyzed"
        
        save_job(db, job)
        log.info(f"  {job.get('company')} — {job.get('title')} — {score}%")
        
        # Decision
        if score >= AUTO_APPLY_THRESHOLD:
            # Auto apply
            success = optimize_and_apply(db, job, cv_text, profile)
            if success:
                auto_applied += 1
                send_telegram(
                    f"✅ <b>AUTO APPLIED</b>\n\n"
                    f"🏢 {job.get('company')}\n"
                    f"💼 {job.get('title')}\n"
                    f"📊 Match: {score}%\n"
                    f"🕐 {datetime.now().strftime('%H:%M')}"
                )
                mark_job_status(db, job.get("id"), "applied")
        
        elif score >= ASK_THRESHOLD:
            needs_approval.append(job)
        
        else:
            low_match += 1
            mark_job_status(db, job.get("id"), "skipped_low_match")
    
    # Step 4: Medium match jobs ke liye Hassan se pucho
    for job in needs_approval[:3]:  # Max 3 per cycle
        send_telegram(
            f"🤔 <b>Apply karna chahiye?</b>\n\n"
            f"🏢 {job.get('company')}\n"
            f"💼 {job.get('title')}\n"
            f"📊 Match: {job.get('match_score')}%\n"
            f"❌ Missing: {', '.join(job.get('missing_skills', [])[:3])}",
            buttons=[
                {"text": "✅ Haan Apply Karo",  "data": f"approve_{job.get('id')}"},
                {"text": "❌ Skip",              "data": f"skip_{job.get('id')}"},
            ]
        )
        time.sleep(1)
    
    # Step 5: Summary
    log.info(f"Cycle complete — Auto: {auto_applied} | Pending: {len(needs_approval)} | Low: {low_match}")
    
    if auto_applied > 0 or needs_approval:
        send_telegram(
            f"📊 <b>Cycle Complete</b>\n\n"
            f"✅ Auto Applied: {auto_applied}\n"
            f"⏳ Approval Needed: {len(needs_approval)}\n"
            f"⏭️ Low Match: {low_match}\n"
            f"🕐 Next cycle: {CYCLE_HOURS} hours"
        )

# ── Telegram Approval Listener ────────────────────────────────
def listen_telegram(db):
    """Hassan ke Yes/No replies sunna"""
    last_update_id = 0
    log.info("👂 Telegram listener started")
    print("[DEBUG] Telegram listener thread is running...")
    
    while True:
        try:
            url    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": last_update_id + 1, "allowed_updates": ["callback_query"]}
            resp   = requests.get(url, params=params, timeout=35)
            
            if resp.status_code != 200:
                print(f"[DEBUG] getUpdates returned {resp.status_code}")
                time.sleep(5)
                continue
            
            updates = resp.json().get("result", [])
            
            for update in updates:
                last_update_id = update["update_id"]
                callback       = update.get("callback_query")
                
                if not callback:
                    continue
                
                cb_data  = callback.get("data", "")
                cb_id    = callback.get("id")
                print(f"[DEBUG] Received callback: {cb_data}")
                
                if cb_data.startswith("approve_"):
                    job_id = cb_data.replace("approve_", "")
                    answer_callback(cb_id, "✅ Processing...")
                    handle_approval(db, job_id, approved=True)
                
                elif cb_data.startswith("skip_"):
                    job_id = cb_data.replace("skip_", "")
                    answer_callback(cb_id, "⏭️ Skipped")
                    handle_approval(db, job_id, approved=False)
        
        except requests.exceptions.Timeout:
            pass  # Normal — long polling timeout
        except Exception as e:
            log.error(f"Telegram listener error: {e}")
            print(f"[DEBUG] Listener exception: {e}")
            time.sleep(5)

def handle_approval(db, job_id, approved):
    """Hassan ki approval handle karo"""
    job = get_pending_job(db, job_id)
    if not job:
        log.error(f"Job not found: {job_id}")
        return
    
    profile = get_user_profile(db)
    cv_text = profile.get("cv_text", "")
    
    if approved:
        send_telegram(f"⏳ Applying to {job.get('company')}...")
        success = optimize_and_apply(db, job, cv_text, profile)
        
        if success:
            send_telegram(f"✅ Applied to {job.get('company')} — {job.get('title')}")
            mark_job_status(db, job_id, "applied")
        else:
            send_telegram(f"⚠️ Apply failed — check manually:\n{job.get('apply_url', '')}")
            mark_job_status(db, job_id, "apply_failed")
    else:
        send_telegram(f"⏭️ Skipped: {job.get('company')} — {job.get('title')}")
        mark_job_status(db, job_id, "skipped_by_user")

# ── MAIN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀 JOBPILOT AGENT MAIN ENTRY POINT")
    log.info("🚀 JobPilot Agent Runner Starting...")
    log.info(f"   Cycle: every {CYCLE_HOURS} hours")
    log.info(f"   Auto-apply threshold: {AUTO_APPLY_THRESHOLD}%")
    log.info(f"   Ask threshold: {ASK_THRESHOLD}%")
    
    # Firebase connect karo
    try:
        print("[DEBUG] Connecting to Firebase...")
        db = get_firebase_db()
        print("[DEBUG] Firebase connected successfully")
    except Exception as e:
        log.error(f"Firebase connection failed: {e}")
        print(f"[DEBUG] Firebase FATAL: {e}")
        exit(1)
    
    # Telegram listener background mein shuru karo
    import threading
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        print("[DEBUG] Starting Telegram listener thread...")
        t = threading.Thread(target=listen_telegram, args=(db,), daemon=True)
        t.start()
        print("[DEBUG] Telegram listener thread started")
    else:
        print("[DEBUG] Telegram not configured — listener not started")
    
    # Startup notification
    print("[DEBUG] Sending startup message via Telegram...")
    result = send_telegram(
        "🚀 <b>JobPilot Agent Started!</b>\n\n"
        f"✅ Firebase: Connected\n"
        f"🔄 Cycle: Har {CYCLE_HOURS} ghante\n"
        f"📊 Auto-apply: {AUTO_APPLY_THRESHOLD}%+ match\n\n"
        "So jao — main kaam kar raha hoon! 😴"
    )
    print(f"[DEBUG] Startup message send result: {result}")
    
    # Main autonomous loop
    cycle_count = 0
    while True:
        cycle_count += 1
        print(f"\n[DEBUG] Starting cycle #{cycle_count}")
        try:
            run_agent_cycle(db)
        except Exception as e:
            log.error(f"Cycle error: {e}")
            send_telegram(f"⚠️ Agent error:\n{str(e)[:200]}")
        
        log.info(f"💤 Sleeping {CYCLE_HOURS} hours...")
        print(f"[DEBUG] Sleeping for {CYCLE_HOURS} hours until next cycle")
        time.sleep(CYCLE_HOURS * 3600)
