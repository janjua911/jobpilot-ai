"""
agents/analyzer_agent.py — Analyzer Agent
==========================================
CV vs Job Description matching using Gemini + ChromaDB

What it does:
  1. Reads CV from Firestore (user's uploaded CV)
  2. Fetches job from Firebase
  3. Compares using Gemini (intelligent matching)
  4. Returns: match_score, matched_skills, missing_skills, free_courses
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import google.generativeai as genai
import streamlit as st

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    """
    CV vs JD matching agent using Gemini Flash 2.0
    """
    
    def __init__(self, gemini_api_key: str = None):
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
        elif os.getenv("GEMINI_API_KEY"):
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        else:
            st.error("GEMINI_API_KEY not found!")
            
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        
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
        Compare CV with Job Description and return match analysis
        
        Returns:
            {
                "match_score": 0-100,
                "matched_skills": ["Python", "ML", ...],
                "missing_skills": ["FastAPI", "AWS", ...],
                "recommendation": "Brief recommendation",
                "free_courses": [
                    {"skill": "FastAPI", "course": "Course name", "url": "..."}
                ],
                "quick_analysis": "Short summary"
            }
        """
        
        prompt = self._build_analysis_prompt(cv_text, jd_text, job_title, company_name)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 2048,
                }
            )
            
            result = self._parse_response(response.text)
            return result
            
        except Exception as e:
            logger.error(f"Gemini analysis error: {e}")
            # Fallback — basic keyword matching
            return self._fallback_analysis(cv_text, jd_text)
    
    # ═══════════════════════════════════════════════════════════
    #  BATCH ANALYSIS — Multiple Jobs
    # ═══════════════════════════════════════════════════════════
    
    def analyze_multiple_jobs(
        self, 
        cv_text: str, 
        jobs: List[Dict],
        progress_callback=None
    ) -> List[Dict]:
        """
        Ek CV ko multiple jobs ke saath compare karo
        """
        analyzed_jobs = []
        total = len(jobs)
        
        for i, job in enumerate(jobs):
            if progress_callback:
                progress_callback(int((i / total) * 100), f"Analyzing: {job.get('title', 'Job')[:30]}...")
            
            jd_text = job.get("description", "")
            if not jd_text:
                jd_text = job.get("job_description", "")
            
            analysis = self.analyze_match(
                cv_text=cv_text,
                jd_text=jd_text[:3000],  # Limit token usage
                job_title=job.get("title", ""),
                company_name=job.get("company", "")
            )
            
            # Merge analysis into job
            job["match_score"] = analysis.get("match_score", 0)
            job["matched_skills"] = analysis.get("matched_skills", [])
            job["missing_skills"] = analysis.get("missing_skills", [])
            job["recommendation"] = analysis.get("recommendation", "")
            job["free_courses"] = analysis.get("free_courses", [])
            job["quick_analysis"] = analysis.get("quick_analysis", "")
            
            analyzed_jobs.append(job)
            
        # Sort by match score
        return sorted(analyzed_jobs, key=lambda x: x.get("match_score", 0), reverse=True)
    
    # ═══════════════════════════════════════════════════════════
    #  SKILL GAP ROADMAP
    # ═══════════════════════════════════════════════════════════
    
    def get_skill_gap_roadmap(self, missing_skills: List[str]) -> List[Dict]:
        """
        Missing skills ke liye free courses suggest karo
        """
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
            response = self.model.generate_content(prompt, generation_config={"temperature": 0.3})
            # Extract JSON from response
            text = response.text
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Skill gap roadmap error: {e}")
            
        return [{"skill": s, "resource": f"Search YouTube/Coursera for {s} tutorials", "estimated_hours": 5} for s in missing_skills[:3]]
    
    # ═══════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════
    
    def _build_analysis_prompt(self, cv_text: str, jd_text: str, job_title: str, company_name: str) -> str:
        """Strict ATS scoring prompt — realistic scores"""
        
        # Truncate to avoid token limits
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

=== STRICT SCORING RULES (FOLLOW CAREFULLY) ===

Score 90-100: PERFECT MATCH (VERY RARE)
- Candidate has EVERY required skill
- Experience years match EXACTLY
- Same industry/domain experience

Score 70-89: STRONG MATCH
- Most key skills present (80%+)
- Experience close to requirement
- Some relevant domain knowledge

Score 50-69: PARTIAL MATCH (MOST COMMON FOR FRESH GRADS)
- Some skills present (50-70%)
- Experience gap of 1-2 years
- Need to learn some technologies

Score 30-49: WEAK MATCH
- Few skills match (<50%)
- Significant experience gap
- Different domain/industry

Score 0-29: POOR MATCH
- Almost nothing matches
- Wrong field entirely

REMEMBER: 
- Fresh graduates typically score 40-65%
- 70%+ is GOOD for entry level
- 90%+ is almost impossible for fresh grads
- Be HONEST and STRICT

=== OUTPUT ===
Return ONLY JSON (no explanations):
{{
    "match_score": <integer 40-75 typical for fresh grad>,
    "matched_skills": ["skill1", "skill2"],
    "missing_skills": ["skill1", "skill2"],
    "recommendation": "<specific advice to improve match>",
    "quick_analysis": "<1-line honest summary>"
}}
"""
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse Gemini response and extract JSON"""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                # Ensure all fields exist
                return {
                    "match_score": result.get("match_score", 50),
                    "matched_skills": result.get("matched_skills", []),
                    "missing_skills": result.get("missing_skills", []),
                    "recommendation": result.get("recommendation", "Consider highlighting relevant skills."),
                    "quick_analysis": result.get("quick_analysis", "Review the detailed analysis above."),
                    "free_courses": result.get("free_courses", [])
                }
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            
        return self._default_analysis()
    
    def _default_analysis(self) -> Dict:
        """Fallback analysis when Gemini fails"""
        return {
            "match_score": 50,
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "Please try again or check API key.",
            "quick_analysis": "Analysis temporarily unavailable.",
            "free_courses": []
        }
    
    def _fallback_analysis(self, cv_text: str, jd_text: str) -> Dict:
        """Simple keyword-based fallback matching with stricter scoring"""
        cv_lower = cv_text.lower() if cv_text else ""
        jd_lower = jd_text.lower() if jd_text else ""
        
        # Common tech skills
        skills = ["python", "java", "javascript", "react", "angular", "vue", "node", "django", 
                  "flask", "fastapi", "aws", "azure", "docker", "kubernetes", "sql", "mongodb",
                  "tensorflow", "pytorch", "machine learning", "ai", "data science"]
        
        matched = []
        for skill in skills:
            if skill in cv_lower and skill in jd_lower:
                matched.append(skill)
                
        missing = []
        for skill in skills:
            if skill in jd_lower and skill not in cv_lower:
                missing.append(skill)
        
        # STRICTER fallback scoring for fresh grads
        if len(matched) == 0:
            score = 0
        elif len(missing) == 0:
            score = 85
        else:
            # Max 75 for fresh grads with partial matches
            score = min(75, int((len(matched) / (len(missing) + len(matched))) * 75))
        
        return {
            "match_score": score,
            "matched_skills": matched[:10],
            "missing_skills": missing[:10],
            "recommendation": f"Add {', '.join(missing[:3])} to your CV if possible." if missing else "Great match!",
            "quick_analysis": f"Matched {len(matched)} skills, missing {len(missing)}",
            "free_courses": []
        }


# ═══════════════════════════════════════════════════════════
#  STREAMLIT HELPER — Batch Analysis for Job Feed
# ═══════════════════════════════════════════════════════════

def analyze_jobs_in_session(db, analyzer: AnalyzerAgent):
    """
    Session mein stored jobs ko analyze karo aur save karo
    """
    jobs = st.session_state.get("jobs_list", [])
    cv_text = st.session_state.get("cv_text", "")
    
    if not cv_text:
        st.warning("⚠️ Pehle CV upload karo — Settings mein jao")
        return False
        
    if not jobs:
        st.warning("⚠️ Pehle Jobs Dhundo button dabao")
        return False
    
    progress_bar = st.progress(0, text="Analyzing jobs...")
    status_text = st.empty()
    
    def update_progress(pct, msg):
        progress_bar.progress(pct / 100, text=msg)
        status_text.caption(msg)
    
    try:
        analyzed = analyzer.analyze_multiple_jobs(
            cv_text=cv_text,
            jobs=jobs,
            progress_callback=update_progress
        )
        
        # Update session
        st.session_state.jobs_list = analyzed
        
        # Save to Firebase
        if db:
            for job in analyzed:
                try:
                    db.collection("jobs").document(job["id"]).set({
                        "match_score": job.get("match_score", 0),
                        "matched_skills": job.get("matched_skills", []),
                        "missing_skills": job.get("missing_skills", []),
                        "recommendation": job.get("recommendation", ""),
                        "analyzed_at": __import__('datetime').datetime.utcnow().isoformat()
                    }, merge=True)
                except Exception as e:
                    logger.warning(f"Save analysis error: {e}")
        
        progress_bar.progress(100, text=f"✅ Analyzed {len(analyzed)} jobs!")
        return True
        
    except Exception as e:
        st.error(f"Analysis error: {e}")
        return False