"""
agents/analyzer_agent.py — Analyzer Agent
==========================================
CV vs Job Description matching using Groq API (primary) + Gemini (fallback)

FIXED:
  - Removed top-level `import streamlit as st` (crashes agent_runner)
  - Replaced st.error() with logger.error()
  - Streamlit imports only inside Streamlit-specific functions
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
# 🔧 DEBUG — Railway environment variables check
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("🚨 [RAILWAY DEBUG] Environment Variables Check")
print(f"GROQ_API_KEY exists: {'YES' if os.getenv('GROQ_API_KEY') else 'NO'}")
print(f"GROQ_API_KEY value: {os.getenv('GROQ_API_KEY', 'MISSING')[:20] if os.getenv('GROQ_API_KEY') else 'NOT SET'}...")
print(f"GEMINI_API_KEY exists: {'YES' if os.getenv('GEMINI_API_KEY') else 'NO'}")
print("=" * 60)

# Initialize API preferences
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_GROQ       = bool(GROQ_API_KEY)

# Only import Gemini if needed
if not USE_GROQ and GEMINI_API_KEY:
    import google.generativeai as genai

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """
    CV vs JD matching agent using Groq (primary) or Gemini (fallback)
    """

    def __init__(self, api_key: str = None):
        self.use_groq = USE_GROQ

        if self.use_groq:
            from groq import Groq
            self.groq_client = Groq(api_key=GROQ_API_KEY)
            self.model = "llama-3.3-70b-versatile"
            logger.info("AnalyzerAgent using Groq API")

        elif GEMINI_API_KEY or api_key:
            import google.generativeai as genai
            genai.configure(api_key=api_key or GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
            logger.info("AnalyzerAgent using Gemini API (fallback)")

        else:
            # ✅ FIX: was st.error() — crashes agent_runner (no Streamlit there)
            logger.error("Neither GROQ_API_KEY nor GEMINI_API_KEY found! Agent cannot analyze jobs.")
            self.use_groq = False

    # ═══════════════════════════════════════════════════════════
    #  MAIN METHOD — CV vs JD Comparison
    # ═══════════════════════════════════════════════════════════

    def analyze_match(
        self,
        cv_text: str,
        jd_text: str,
        job_title: str = "",
        company_name: str = ""
    ) -> Dict:
        """
        Compare CV with Job Description and return match analysis.

        Returns:
            {
                "match_score": 0-100,
                "matched_skills": [...],
                "missing_skills": [...],
                "recommendation": "...",
                "free_courses": [...],
                "quick_analysis": "..."
            }
        """
        prompt = self._build_analysis_prompt(cv_text, jd_text, job_title, company_name)

        try:
            if self.use_groq:
                response_text = self._call_groq(prompt)
            else:
                response_text = self._call_gemini(prompt)

            return self._parse_response(response_text)

        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return self._fallback_analysis(cv_text, jd_text)

    def _call_groq(self, prompt: str) -> str:
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict ATS analyzer. Return ONLY valid JSON."},
                    {"role": "user",   "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def _call_gemini(self, prompt: str) -> str:
        response = self.gemini_model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 1000}
        )
        return response.text

    # ═══════════════════════════════════════════════════════════
    #  BATCH ANALYSIS — Multiple Jobs
    # ═══════════════════════════════════════════════════════════

    def analyze_multiple_jobs(
        self,
        cv_text: str,
        jobs: List[Dict],
        progress_callback=None
    ) -> List[Dict]:
        analyzed_jobs = []
        total = len(jobs)

        for i, job in enumerate(jobs):
            if progress_callback:
                progress_callback(int((i / total) * 100), f"Analyzing: {job.get('title', 'Job')[:30]}...")

            jd_text  = job.get("description", "") or job.get("job_description", "")
            analysis = self.analyze_match(
                cv_text      = cv_text,
                jd_text      = jd_text[:3000],
                job_title    = job.get("title", ""),
                company_name = job.get("company", "")
            )

            job["match_score"]    = analysis.get("match_score", 0)
            job["matched_skills"] = analysis.get("matched_skills", [])
            job["missing_skills"] = analysis.get("missing_skills", [])
            job["recommendation"] = analysis.get("recommendation", "")
            job["free_courses"]   = analysis.get("free_courses", [])
            job["quick_analysis"] = analysis.get("quick_analysis", "")
            analyzed_jobs.append(job)

        return sorted(analyzed_jobs, key=lambda x: x.get("match_score", 0), reverse=True)

    # ═══════════════════════════════════════════════════════════
    #  SKILL GAP ROADMAP
    # ═══════════════════════════════════════════════════════════

    def get_skill_gap_roadmap(self, missing_skills: List[str]) -> List[Dict]:
        if not missing_skills:
            return []

        prompt = f"""
For each missing skill below, suggest ONE free learning resource.
Missing skills: {', '.join(missing_skills[:5])}

Return JSON array only (no other text):
[
    {{
        "skill": "skill name",
        "resource": "course/tutorial name",
        "platform": "Coursera/YouTube/FreeCodeCamp",
        "estimated_hours": number
    }}
]
"""
        try:
            response_text = self._call_groq(prompt) if self.use_groq else self._call_gemini(prompt)
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Skill gap roadmap error: {e}")

        return [
            {"skill": s, "resource": f"Search YouTube/Coursera for {s} tutorials",
             "platform": "Various", "estimated_hours": 5}
            for s in missing_skills[:3]
        ]

    # ═══════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════

    def _build_analysis_prompt(self, cv_text, jd_text, job_title, company_name) -> str:
        cv_preview = cv_text[:2000] if cv_text else "No CV uploaded"
        jd_preview = jd_text[:2000] if jd_text else "No JD found"

        return f"""
You are a STRICT ATS (Applicant Tracking System) analyzer. Be TOUGH and REALISTIC.

=== CANDIDATE CV ===
{cv_preview}

=== JOB DESCRIPTION ===
Title: {job_title}
Company: {company_name}
{jd_preview}

=== STRICT SCORING RULES ===
90-100: PERFECT MATCH (very rare for fresh grads)
70-89:  STRONG MATCH — most key skills present
50-69:  PARTIAL MATCH — some skills, some gap
30-49:  WEAK MATCH — significant gap
0-29:   POOR MATCH — wrong field

REMEMBER: Fresh graduates typically score 40-65%. Be HONEST and STRICT.

=== OUTPUT — Return ONLY valid JSON, no markdown ===
{{
    "match_score": <integer>,
    "matched_skills": ["skill1", "skill2"],
    "missing_skills": ["skill1", "skill2"],
    "recommendation": "<1-2 sentences>",
    "quick_analysis": "<1 line summary>"
}}
"""

    def _parse_response(self, response_text: str) -> Dict:
        try:
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "match_score":    min(100, max(0, result.get("match_score", 50))),
                    "matched_skills": result.get("matched_skills", [])[:15],
                    "missing_skills": result.get("missing_skills", [])[:15],
                    "recommendation": result.get("recommendation", "Consider highlighting relevant skills."),
                    "quick_analysis": result.get("quick_analysis", "Review analysis above."),
                    "free_courses":   result.get("free_courses", [])
                }
        except Exception as e:
            logger.warning(f"Parse error: {e} | Response: {response_text[:200]}")

        return self._default_analysis()

    def _default_analysis(self) -> Dict:
        return {
            "match_score": 50, "matched_skills": [], "missing_skills": [],
            "recommendation": "Please try again or check API configuration.",
            "quick_analysis": "Analysis temporarily unavailable.", "free_courses": []
        }

    def _fallback_analysis(self, cv_text: str, jd_text: str) -> Dict:
        cv_lower = cv_text.lower() if cv_text else ""
        jd_lower = jd_text.lower() if jd_text else ""

        skills = [
            "python", "java", "javascript", "react", "angular", "vue", "node", "django",
            "flask", "fastapi", "aws", "azure", "gcp", "docker", "kubernetes", "sql",
            "mongodb", "postgresql", "tensorflow", "pytorch", "machine learning",
            "deep learning", "ai", "data science", "pandas", "numpy", "scikit-learn",
            "git", "linux", "rest api", "html", "css", "typescript", "nextjs",
            "spring boot", "c++", "c#", "php"
        ]

        matched = [s for s in skills if s in cv_lower and s in jd_lower]
        missing = [s for s in skills if s in jd_lower and s not in cv_lower]

        if not matched:
            score = 0
        elif not missing:
            score = 85
        else:
            ratio = len(matched) / (len(missing) + len(matched))
            score = min(75, int(ratio * 75))

        if cv_text and len(cv_text) > 500:
            score = min(75, score + 10)

        return {
            "match_score":    score,
            "matched_skills": matched[:10],
            "missing_skills": missing[:10],
            "recommendation": f"Add {', '.join(missing[:3])} to your CV if possible." if missing else "Great match!",
            "quick_analysis": f"Matched {len(matched)} skills, missing {len(missing)}.",
            "free_courses":   []
        }


# ═══════════════════════════════════════════════════════════
#  STREAMLIT HELPER — Only used inside Streamlit context
# ═══════════════════════════════════════════════════════════

def analyze_jobs_in_session(db, analyzer: AnalyzerAgent):
    """
    Analyze jobs stored in Streamlit session and save results.
    NOTE: This function is ONLY called from Streamlit pages — st import is safe here.
    """
    import streamlit as st  # ✅ Local import — won't crash agent_runner

    jobs    = st.session_state.get("jobs_list", [])
    cv_text = st.session_state.get("cv_text", "")

    if not cv_text:
        st.warning("⚠️ Please upload your CV first — Go to Settings")
        return False

    if not jobs:
        st.warning("⚠️ Please search for jobs first — Click 'Find Jobs' button")
        return False

    progress_bar = st.progress(0, text="Analyzing jobs...")
    status_text  = st.empty()

    def update_progress(pct, msg):
        progress_bar.progress(pct / 100, text=msg)
        status_text.caption(msg)

    try:
        analyzed = analyzer.analyze_multiple_jobs(
            cv_text           = cv_text,
            jobs              = jobs,
            progress_callback = update_progress
        )

        st.session_state.jobs_list         = analyzed
        st.session_state.analysis_complete = True

        if db:
            for job in analyzed:
                try:
                    job_id = job.get("id") or job.get("job_id")
                    if job_id:
                        db.collection("jobs").document(str(job_id)).set({
                            "match_score":    job.get("match_score", 0),
                            "matched_skills": job.get("matched_skills", []),
                            "missing_skills": job.get("missing_skills", []),
                            "recommendation": job.get("recommendation", ""),
                            "analyzed_at":    __import__('datetime').datetime.utcnow().isoformat()
                        }, merge=True)
                except Exception as e:
                    logger.warning(f"Save analysis error: {e}")

        high_match = len([j for j in analyzed if j.get("match_score", 0) >= 70])
        progress_bar.progress(100, text=f"✅ Analyzed {len(analyzed)} jobs!")
        status_text.success(f"✅ Analysis complete! Found {high_match} high-match jobs.")
        return True

    except Exception as e:
        st.error(f"Analysis error: {e}")
        logger.error(f"Batch analysis error: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════

def get_analyzer_status() -> Dict:
    return {
        "using_groq":      USE_GROQ,
        "groq_available":  bool(GROQ_API_KEY),
        "gemini_available": bool(GEMINI_API_KEY),
        "model":           "llama-3.3-70b-versatile" if USE_GROQ else "gemini-2.0-flash"
    }
