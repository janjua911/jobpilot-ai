"""
agents/optimizer_agent.py — Optimizer Agent
CV Tailoring and Cover Letter Generation for Specific Jobs
"""

import os
import io
import re
import logging
from typing import Dict, List
from datetime import datetime

import google.generativeai as genai
import streamlit as st
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)


class OptimizerAgent:
    
    def __init__(self, gemini_api_key: str = None):
        api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")
    
    def optimize_cv_for_job(
        self,
        cv_text: str,
        jd_text: str,
        job_title: str,
        company_name: str,
        candidate_name: str = "Candidate"
    ) -> Dict:
        
        keywords = self._extract_keywords(jd_text)
        optimized_cv = self._rewrite_cv(cv_text, jd_text, keywords)
        cover_letter = self._generate_cover_letter(
            candidate_name, job_title, company_name, jd_text, cv_text
        )
        docx_bytes = self._create_docx(
            optimized_cv, candidate_name, job_title, company_name
        )
        
        return {
            "cv_docx": docx_bytes,
            "cv_text": optimized_cv,
            "cover_letter": cover_letter,
            "improvement_score": self._calculate_improvement(cv_text, optimized_cv, keywords),
            "keywords_injected": keywords[:10]
        }
    
    def _rewrite_cv(self, cv_text: str, jd_text: str, keywords: List[str]) -> str:
        prompt = f"""
Rewrite this CV to be ATS-friendly for the job.

CV: {cv_text[:2000]}

Keywords: {', '.join(keywords[:15])}

Rules: Keep structure, inject keywords naturally, action verbs, quantified results.
Return ONLY the rewritten CV.
"""
        try:
            response = self.model.generate_content(prompt, generation_config={"temperature": 0.4})
            return response.text
        except:
            return cv_text
    
    def _extract_keywords(self, jd_text: str) -> List[str]:
        prompt = f"Extract top 15 technical skills from: {jd_text[:1500]}\nReturn comma-separated list only."
        try:
            response = self.model.generate_content(prompt, generation_config={"temperature": 0.1})
            return [k.strip() for k in response.text.split(',')][:15]
        except:
            return ["Python", "Communication", "Problem Solving"]
    
    def _generate_cover_letter(self, name: str, job_title: str, company: str, jd_text: str, cv_text: str) -> str:
        """Generate detailed personalized cover letter (150-200 words)"""
        
        from datetime import datetime
        
        prompt = f"""
Write a DETAILED cover letter (150-200 words) for {name} applying for {job_title} at {company}.

=== JOB DESCRIPTION ===
{jd_text[:800]}

=== CANDIDATE SKILLS ===
{cv_text[:600]}

=== STRUCTURE (MUST FOLLOW) ===

Paragraph 1 (3-4 sentences):
- Express enthusiasm for {company} and this specific role
- Mention what excites you about their work

Paragraph 2 (4-5 sentences):
- List 2-3 specific skills from CV that match the job
- Give a BRIEF example of using each skill
- Connect directly to job requirements

Paragraph 3 (2-3 sentences):
- Why you'd be a great fit
- Request for interview
- Thank the reader

=== REQUIREMENTS ===
- Length: 150-200 words
- Professional but warm tone
- Use specific details from CV
- No markdown, no bullet points

RETURN ONLY THE LETTER:

{datetime.now().strftime('%B %d, %Y')}

Hiring Manager
{company}

Dear Hiring Manager,

[Write 150-200 word letter here]

Sincerely,
{name}
"""
        
        try:
            response = self.model.generate_content(
                prompt, 
                generation_config={"temperature": 0.5, "max_output_tokens": 800}
            )
            letter = response.text.strip()
            
            # Check if letter is too short (<100 words)
            if len(letter.split()) < 100:
                # Fallback to longer template
                return f"""{datetime.now().strftime('%B %d, 2025')}

Hiring Manager
{company}

Dear Hiring Manager,

I am writing to enthusiastically apply for the {job_title} position at {company}. Your work in {jd_text[:100]} particularly excites me, as it aligns with my background in AI/ML development.

My experience includes developing Python-based applications with machine learning models, achieving 90%+ accuracy in computer vision tasks. I have deployed production-ready systems using cloud platforms (AWS) and containerization (Docker), which directly matches your requirements for scalable ML systems.

In my recent project TalentHire, I built an AI-powered CV screening platform that reduced screening time by 95% using NLP and scikit-learn. This experience in end-to-end ML deployment would allow me to contribute immediately to your engineering team.

I am particularly drawn to {company} because of your innovative approach to solving real-world problems. I would welcome the opportunity to discuss how my skills can benefit your team. Thank you for your consideration and time.

Sincerely,
{name}"""
            
            return letter
            
        except Exception as e:
            logger.error(f"Cover letter error: {e}")
            return f"""{datetime.now().strftime('%B %d, 2025')}

Hiring Manager
{company}

Dear Hiring Manager,

I am excited to apply for the {job_title} position at {company}. 

With my background in {cv_text[:200]}, I am confident I can contribute effectively to your team. I have experience with Python, machine learning, and cloud deployment, and have successfully delivered multiple AI projects from concept to production.

I look forward to discussing how I can add value to {company}.

Sincerely,
{name}"""
    
    def _create_docx(self, cv_text: str, name: str, job_title: str, company: str) -> bytes:
        """Create ATS-friendly DOCX file with actual user name"""
        
        doc = Document()
        
        # Set margins
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)
        
        # ✅ Use actual name, not "Candidate"
        # If name is "Candidate" or empty, use a default name
        if not name or name == "Candidate":
            display_name = st.session_state.get("user_name", "Hassan Afzal")
        else:
            display_name = name
        
        title = doc.add_heading(display_name, level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add contact line (customizable)
        contact = doc.add_paragraph()
        contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact.add_run("📍 Location | 📧 email@example.com | 🔗 linkedin.com/in/profile")
        
        doc.add_paragraph()
        
        # Rest of CV content
        lines = cv_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('##') or (line.isupper() and len(line) < 30):
                doc.add_heading(line.replace('##', '').strip(), level=2)
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                doc.add_paragraph(line, style='List Bullet')
            else:
                doc.add_paragraph(line)
        
        byte_io = io.BytesIO()
        doc.save(byte_io)
        byte_io.seek(0)
        return byte_io.getvalue()
    
    def _calculate_improvement(self, original: str, optimized: str, keywords: List[str]) -> int:
        original_lower = original.lower()
        optimized_lower = optimized.lower()
        new_keywords = [kw for kw in keywords if kw.lower() in optimized_lower and kw.lower() not in original_lower]
        return min(100, int((len(new_keywords) / max(len(keywords), 1)) * 100))


def show_optimizer_ui(job: Dict, db):
    """Display optimizer UI with better cover letter display and copy functionality"""
    
    st.markdown("---")
    st.markdown("### ✏️ Tailor CV for this Job")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(f"📄 Generate Tailored CV", key=f"optimize_{job['id']}"):
            cv_text = st.session_state.get("cv_text", "")
            if not cv_text:
                st.warning("⚠️ Pehle Settings mein CV upload karo!")
                return
            
            with st.spinner("🤖 Generating tailored CV and cover letter... (takes 10-15 seconds)"):
                optimizer = OptimizerAgent()
                result = optimizer.optimize_cv_for_job(
                    cv_text=cv_text,
                    jd_text=job.get("description", ""),
                    job_title=job.get("title", ""),
                    company_name=job.get("company", ""),
                    candidate_name=st.session_state.get("user_name", "Candidate")
                )
                st.session_state[f"optimized_cv_{job['id']}"] = result
                st.success(f"✅ CV optimized! {result['improvement_score']}% improvement")
                st.rerun()
    
    with col2:
        result = st.session_state.get(f"optimized_cv_{job['id']}")
        if result:
            filename = f"{job.get('company', 'Job')}_{job.get('title', 'Role')}_CV.docx"
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            st.download_button(
                label="⬇️ Download Tailored CV (DOCX)",
                data=result["cv_docx"],
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"download_{job['id']}"
            )
            
            # Better cover letter display with copy button
            st.markdown("---")
            st.markdown("### 📝 Cover Letter")
            
            cover_text = result.get("cover_letter", "No cover letter generated")
            
            # Display in text area
            st.text_area(
                label="Cover Letter",
                value=cover_text,
                height=400,
                key=f"cover_{job['id']}",
                label_visibility="collapsed"
            )
            
            # Show word count
            word_count = len(cover_text.split())
            if word_count < 100:
                st.warning(f"⚠️ Cover letter is {word_count} words (recommended: 150-200). Click Regenerate for better result.")
            else:
                st.caption(f"📝 {word_count} words")
            
            # ✅ Copy button with instructions
            copy_col1, copy_col2, copy_col3 = st.columns([1, 2, 1])
            with copy_col1:
                if st.button("📋 Copy to Clipboard", key=f"copy_{job['id']}"):
                    st.info("💡 Select all text above (Ctrl+A), then press Ctrl+C to copy")
            
            with copy_col2:
                st.caption("💡 Tip: Select text → Ctrl+C to copy, then paste into your email/application")
            
            # Show keywords added
            keywords = result.get("keywords_injected", [])
            if keywords:
                st.caption(f"✨ Keywords added to CV: {', '.join(keywords[:8])}")