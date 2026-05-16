"""
cv_storage.py — CV Text Storage (Firestore, Free)
==================================================
Firebase Storage ki jagah CV text seedha Firestore mein.
Cost: $0 — Firestore text documents free hain.

How it works:
  User uploads PDF/DOCX
  → We extract text (python)
  → Store text string in Firestore users/{userId}/cv_text
  → Agents read text from Firestore (no file needed)

Generated CV files (DOCX/PDF):
  → In-memory generate karo
  → User ko direct download button do
  → Server pe save nahi karte
"""

import io
import logging
from datetime import datetime
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  CV TEXT EXTRACTION  (uploaded file se)
# ─────────────────────────────────────────────
def extract_text_from_upload(uploaded_file) -> str:
    """
    Streamlit uploaded file se plain text nikalo.
    PDF aur DOCX dono support karta hai.
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    try:
        if filename.endswith(".pdf"):
            return _extract_pdf(file_bytes)
        elif filename.endswith(".docx"):
            return _extract_docx(file_bytes)
        else:
            st.error("Sirf PDF ya DOCX upload karo")
            return ""
    except Exception as e:
        st.error(f"CV read error: {e}")
        logger.error(f"CV extraction failed: {e}")
        return ""


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(
            page.extract_text() for page in reader.pages
            if page.extract_text()
        )
        return text.strip()
    except ImportError:
        st.error("pypdf install karo: pip install pypdf")
        return ""


def _extract_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(
            para.text for para in doc.paragraphs
            if para.text.strip()
        )
    except ImportError:
        st.error("python-docx install karo: pip install python-docx")
        return ""


# ─────────────────────────────────────────────
#  FIRESTORE CV SAVE / LOAD
# ─────────────────────────────────────────────
def save_cv_to_firestore(db, user_id: str, cv_text: str, filename: str) -> bool:
    """
    CV text Firestore mein save karo.
    Firebase Storage use nahi hota — completely free.
    """
    try:
        db.collection("users").document(user_id).set({
            "cv_text":       cv_text,
            "cv_filename":   filename,
            "cv_updated_at": datetime.utcnow().isoformat(),
            "cv_length":     len(cv_text),
        }, merge=True)
        logger.info(f"CV saved to Firestore for user: {user_id}")
        return True
    except Exception as e:
        logger.error(f"CV save error: {e}")
        return False


def load_cv_from_firestore(db, user_id: str) -> Optional[str]:
    """Firestore se CV text load karo."""
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("cv_text")
    except Exception as e:
        logger.error(f"CV load error: {e}")
    return None


# ─────────────────────────────────────────────
#  GENERATED CV — DIRECT DOWNLOAD (No storage)
# ─────────────────────────────────────────────
def offer_cv_download(docx_bytes: bytes, filename: str) -> None:
    """
    Generated CV ko direct download button ke saath do.
    Server pe kuch save nahi hota.
    """
    st.download_button(
        label="⬇️ Download Tailored CV (DOCX)",
        data=docx_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def offer_pdf_download(pdf_bytes: bytes, filename: str) -> None:
    """PDF version direct download."""
    st.download_button(
        label="⬇️ Download CV (PDF)",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )
