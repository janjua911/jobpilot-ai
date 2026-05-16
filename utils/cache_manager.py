"""
cache_manager.py — Gemini API Response Cache
=============================================
Bottleneck #1 Fix: Gemini 15 req/min limit

How it works:
  1. Hash karo (prompt + model)  →  unique cache key
  2. Firebase mein check karo    →  pehle se hai?
  3. Hit  → return instantly     →  0 Gemini calls used
  4. Miss → Gemini call          →  result Firebase mein save karo

Result: Same JD type ke liye dobara Gemini call NEVER hoti.
Cost: $0 (Firebase free tier pe fit ho jata hai easily)
"""

import hashlib
import json
import time
import logging
from typing import Optional
from datetime import datetime, timedelta

import google.generativeai as genai
import firebase_admin
from firebase_admin import firestore

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
CACHE_COLLECTION   = "gemini_cache"   # Firestore collection name
CACHE_TTL_HOURS    = 24               # Cache kitne ghante valid rahega
MAX_CACHE_ENTRIES  = 5000             # Firebase free tier ke andar rakho
RATE_LIMIT_PER_MIN = 14               # 15 hai limit, 14 use karo (safety margin)


# ─────────────────────────────────────────────
#  RATE LIMITER  (in-memory, per session)
# ─────────────────────────────────────────────
class RateLimiter:
    """
    Simple token-bucket rate limiter.
    15 req/min ke andar rakho — crash nahi karega.
    """
    def __init__(self, max_per_minute: int = RATE_LIMIT_PER_MIN):
        self.max_per_minute = max_per_minute
        self.calls: list[float] = []   # timestamps of recent calls

    def wait_if_needed(self) -> float:
        """
        Agar rate limit hit ho rahi ho → auto-wait.
        Returns: seconds waited (0 agar wait nahi karna pada)
        """
        now = time.time()
        # 60 second window ke bahar ki calls hatao
        self.calls = [t for t in self.calls if now - t < 60]

        if len(self.calls) >= self.max_per_minute:
            # Oldest call ke 60 sec baad wait karo
            wait_time = 60 - (now - self.calls[0]) + 0.5  # 0.5 sec buffer
            logger.warning(f"Rate limit approaching — waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self.calls = []  # Reset after wait

        self.calls.append(time.time())
        return 0


# Single instance — module level (survives across Streamlit reruns)
_rate_limiter = RateLimiter()


# ─────────────────────────────────────────────
#  CACHE MANAGER
# ─────────────────────────────────────────────
class GeminiCacheManager:
    """
    Gemini API calls ko cache karta hai Firebase mein.
    
    Usage:
        cache = GeminiCacheManager(gemini_api_key="YOUR_KEY")
        
        result = cache.generate(
            prompt="Analyze this CV against JD...",
            task_type="cv_analysis"   # grouping ke liye
        )
    """

    def __init__(self, gemini_api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=gemini_api_key)
        self.model      = genai.GenerativeModel(model_name)
        self.model_name = model_name
        self.db         = firestore.client()
        self.cache_ref  = self.db.collection(CACHE_COLLECTION)

    # ── Public API ────────────────────────────
    def generate(
        self,
        prompt: str,
        task_type: str = "general",
        temperature: float = 0.7,
        force_refresh: bool = False,
    ) -> str:
        """
        Main method — cache check karo, zarurat ho toh Gemini call karo.

        Args:
            prompt:        Full prompt text
            task_type:     e.g. "cv_analysis", "cover_letter", "skill_gap"
            temperature:   Gemini temperature (0 = deterministic, cache zyada useful)
            force_refresh: True → cache ignore karo, fresh call karo

        Returns:
            str: Gemini response text
        """
        cache_key = self._make_key(prompt, temperature)

        # ── Cache check ──
        if not force_refresh:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"[CACHE HIT] task={task_type} key={cache_key[:12]}...")
                return cached

        # ── Rate limit check ──
        _rate_limiter.wait_if_needed()

        # ── Gemini API call ──
        logger.info(f"[CACHE MISS] task={task_type} → calling Gemini")
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
            result_text = response.text

            # ── Save to cache ──
            self._save_to_cache(cache_key, result_text, task_type)
            return result_text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def get_cache_stats(self) -> dict:
        """Dashboard ke liye cache stats return karo."""
        try:
            docs = self.cache_ref.limit(MAX_CACHE_ENTRIES).get()
            total = len(docs)
            valid = sum(
                1 for d in docs
                if self._is_valid(d.to_dict().get("expires_at"))
            )
            return {
                "total_entries":   total,
                "valid_entries":   valid,
                "expired_entries": total - valid,
                "cache_hit_rate":  self._estimate_hit_rate(),
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {}

    def clear_expired(self) -> int:
        """
        Expired cache entries hata do — Firebase free tier clean rakhne ke liye.
        Isko weekly ek baar chalao (ya Streamlit sidebar button se).
        Returns: Number of deleted entries
        """
        now = datetime.utcnow()
        expired = (
            self.cache_ref
            .where("expires_at", "<", now)
            .limit(500)
            .get()
        )
        count = 0
        for doc in expired:
            doc.reference.delete()
            count += 1
        logger.info(f"Cleared {count} expired cache entries")
        return count

    # ── Private helpers ───────────────────────
    def _make_key(self, prompt: str, temperature: float) -> str:
        """Prompt + model → deterministic cache key (SHA-256)."""
        content = f"{self.model_name}|{temperature}|{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[str]:
        """Firebase se cache entry fetch karo."""
        try:
            doc = self.cache_ref.document(key).get()
            if not doc.exists:
                return None
            data = doc.to_dict()
            if not self._is_valid(data.get("expires_at")):
                return None  # Expired
            return data.get("response")
        except Exception as e:
            logger.warning(f"Cache read error (non-fatal): {e}")
            return None  # Cache miss on error — graceful degradation

    def _save_to_cache(self, key: str, response: str, task_type: str) -> None:
        """Response ko Firebase mein save karo."""
        try:
            self.cache_ref.document(key).set({
                "response":   response,
                "task_type":  task_type,
                "model":      self.model_name,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=CACHE_TTL_HOURS),
            })
        except Exception as e:
            logger.warning(f"Cache write error (non-fatal): {e}")
            # Write fail ho — koi baat nahi, next call fresh hoga

    @staticmethod
    def _is_valid(expires_at) -> bool:
        """Check karo cache entry abhi valid hai."""
        if expires_at is None:
            return False
        if hasattr(expires_at, "replace"):          # datetime object
            return expires_at > datetime.utcnow()
        return False

    def _estimate_hit_rate(self) -> str:
        """Simple hit rate — production mein proper counter lagao."""
        return "Track via Streamlit st.session_state counters"


# ─────────────────────────────────────────────
#  TASK-SPECIFIC WRAPPERS
#  (agent files mein inhe import karo — simple)
# ─────────────────────────────────────────────

def analyze_cv_vs_jd(cache: GeminiCacheManager, cv_text: str, jd_text: str) -> str:
    """Analyzer Agent ke liye — CV vs JD match analysis."""
    prompt = f"""
You are an expert ATS analyzer. Compare this CV against the Job Description.

CV:
{cv_text}

Job Description:
{jd_text}

Return a JSON object with:
{{
  "match_score": <0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],
  "recommendation": "brief 2-line recommendation",
  "free_courses": [{{"skill": "X", "course": "Coursera link"}}]
}}
Return ONLY the JSON. No extra text.
"""
    return cache.generate(prompt, task_type="cv_analysis", temperature=0.2)


def optimize_cv_bullet(cache: GeminiCacheManager, bullet: str, jd_keywords: list[str]) -> str:
    """Optimizer Agent ke liye — single CV bullet rewrite."""
    keywords_str = ", ".join(jd_keywords[:10])  # Top 10 keywords
    prompt = f"""
Rewrite this CV bullet point to be ATS-friendly and include relevant keywords.

Original bullet: {bullet}
Target keywords: {keywords_str}

Rules:
- Start with a strong action verb
- Include a quantified result if possible
- Keep under 20 words
- Sound natural, not keyword-stuffed

Return ONLY the rewritten bullet. Nothing else.
"""
    return cache.generate(prompt, task_type="cv_optimize", temperature=0.4)


def generate_cover_letter(
    cache: GeminiCacheManager,
    candidate_name: str,
    jd_text: str,
    cv_summary: str,
    company_name: str,
) -> str:
    """Optimizer Agent ke liye — cover letter generation."""
    prompt = f"""
Write a professional cover letter for {candidate_name} applying to {company_name}.

Job Description Summary:
{jd_text[:500]}

Candidate Background:
{cv_summary[:500]}

Rules:
- 3 paragraphs maximum
- First: why this role excites them
- Second: top 2 matching skills with evidence
- Third: call to action
- Professional but warm tone
- Under 250 words
"""
    return cache.generate(prompt, task_type="cover_letter", temperature=0.6)


def get_skill_gap_roadmap(cache: GeminiCacheManager, missing_skills: list[str]) -> str:
    """Tracker Agent ke liye — skill gap se free course roadmap."""
    skills_str = "\n".join(f"- {s}" for s in missing_skills[:5])
    prompt = f"""
For each missing skill below, suggest ONE free learning resource.

Missing skills:
{skills_str}

Return JSON array:
[
  {{
    "skill": "skill name",
    "resource": "course/tutorial name",
    "url": "https://...",
    "estimated_hours": <number>
  }}
]
Return ONLY the JSON array.
"""
    return cache.generate(prompt, task_type="skill_gap", temperature=0.3)
