"""
vector_store.py — ChromaDB Persistent Setup
============================================
Bottleneck #3 Fix: ChromaDB In-Memory → Disk Persistent

ONE LINE CHANGE that prevents RAM crash:
  Before: chromadb.Client()              ← RAM mein, restart pe wipe
  After:  chromadb.PersistentClient()    ← Disk pe, restarts survive karta hai

Also includes:
  - Streamlit @st.cache_resource decorator  (Bottleneck #2 partial fix)
    → ChromaDB client ek baar banta hai, har rerun pe nahi
  - Safe collection get-or-create pattern
  - Batch embedding helper (rate limit friendly)
"""

import os
import time
import logging
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions
import streamlit as st

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
CHROMA_PERSIST_PATH = "./chroma_db"        # Streamlit Share pe /tmp/chroma_db use karo
CV_COLLECTION       = "cv_embeddings"
JD_COLLECTION       = "jd_embeddings"
EMBED_BATCH_SIZE    = 10                   # Gemini embedding rate limit ke andar
EMBED_DELAY_SEC     = 0.5                  # Batches ke beech delay


# ─────────────────────────────────────────────
#  STREAMLIT-CACHED CLIENT
#  @st.cache_resource → client ek baar banta hai per session
#  Bottleneck #2 ka partial fix — Streamlit rerun pe re-init nahi hota
# ─────────────────────────────────────────────
@st.cache_resource
def get_chroma_client() -> chromadb.PersistentClient:
    """
    Disk-backed ChromaDB client.
    
    Streamlit Share pe:
      - /tmp/chroma_db use karo (writable hai)
      - App restart pe data survive karta hai (same deployment mein)
    
    Local development pe:
      - ./chroma_db folder ban jata hai project root mein
    """
    persist_path = os.getenv("CHROMA_PATH", CHROMA_PERSIST_PATH)
    
    # Streamlit Share detection
    if os.getenv("IS_STREAMLIT_SHARE"):
        persist_path = "/tmp/chroma_db"
    
    os.makedirs(persist_path, exist_ok=True)
    logger.info(f"ChromaDB initialized at: {persist_path}")
    
    return chromadb.PersistentClient(path=persist_path)  # THE KEY LINE


@st.cache_resource
def get_embedding_function(gemini_api_key: str):
    """Google Generative AI embeddings — free tier mein available."""
    return embedding_functions.GoogleGenerativeAiEmbeddingFunction(
        api_key=gemini_api_key,
        model_name="models/embedding-001"   # Free, fast
    )


# ─────────────────────────────────────────────
#  VECTOR STORE CLASS
# ─────────────────────────────────────────────
class JobPilotVectorStore:
    """
    ChromaDB wrapper for JobPilot AI.
    
    Usage:
        vs = JobPilotVectorStore(gemini_api_key="YOUR_KEY")
        
        # CV store karo
        vs.store_cv(user_id="hassan_123", cv_text="Full CV text...")
        
        # JD match karo
        results = vs.match_cv_to_jds(user_id="hassan_123", top_k=5)
    """

    def __init__(self, gemini_api_key: str):
        self.client    = get_chroma_client()
        self.embed_fn  = get_embedding_function(gemini_api_key)
        
        # Collections — get_or_create (idempotent, safe)
        self.cv_collection = self.client.get_or_create_collection(
            name=CV_COLLECTION,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"}   # Cosine similarity for text
        )
        self.jd_collection = self.client.get_or_create_collection(
            name=JD_COLLECTION,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"}
        )

    # ── CV Operations ─────────────────────────
    def store_cv(self, user_id: str, cv_text: str, metadata: Optional[dict] = None) -> None:
        """
        User ka CV embed karke ChromaDB mein store karo.
        Upsert use karo — pehle se hai toh update, nahi hai toh add.
        """
        meta = {"user_id": user_id, "type": "cv", **(metadata or {})}
        self.cv_collection.upsert(
            documents=[cv_text],
            ids=[f"cv_{user_id}"],
            metadatas=[meta]
        )
        logger.info(f"CV stored for user: {user_id}")

    def get_cv(self, user_id: str) -> Optional[str]:
        """User ka stored CV text wapas lao."""
        try:
            result = self.cv_collection.get(ids=[f"cv_{user_id}"])
            if result["documents"]:
                return result["documents"][0]
        except Exception:
            pass
        return None

    # ── JD Operations ─────────────────────────
    def store_jds_batch(self, jd_list: list[dict]) -> None:
        """
        Multiple JDs batch mein store karo — rate limit friendly.
        
        jd_list format:
            [{"id": "job_123", "text": "JD text...", "company": "Google"}, ...]
        """
        for i in range(0, len(jd_list), EMBED_BATCH_SIZE):
            batch = jd_list[i : i + EMBED_BATCH_SIZE]
            self.jd_collection.upsert(
                documents=[j["text"] for j in batch],
                ids=[j["id"] for j in batch],
                metadatas=[
                    {k: v for k, v in j.items() if k != "text"}
                    for j in batch
                ]
            )
            if i + EMBED_BATCH_SIZE < len(jd_list):
                time.sleep(EMBED_DELAY_SEC)   # Rate limit respect karo
        logger.info(f"Stored {len(jd_list)} JDs in ChromaDB")

    def store_single_jd(self, job_id: str, jd_text: str, metadata: Optional[dict] = None) -> None:
        """Single JD store karo."""
        meta = {"job_id": job_id, "type": "jd", **(metadata or {})}
        self.jd_collection.upsert(
            documents=[jd_text],
            ids=[job_id],
            metadatas=[meta]
        )

    # ── Matching ──────────────────────────────
    def match_cv_to_jds(
        self,
        user_id: str,
        top_k: int = 10,
        min_score: float = 0.6,
    ) -> list[dict]:
        """
        User ke CV ko saare stored JDs se match karo.
        
        Returns: List of {job_id, score, metadata} sorted by score desc
        """
        cv_text = self.get_cv(user_id)
        if not cv_text:
            logger.warning(f"No CV found for user {user_id}")
            return []

        results = self.jd_collection.query(
            query_texts=[cv_text],
            n_results=min(top_k, self.jd_collection.count() or 1),
            include=["metadatas", "distances", "documents"]
        )

        matches = []
        for i, (doc, dist, meta) in enumerate(zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        )):
            score = 1 - dist  # Cosine distance → similarity score
            if score >= min_score:
                matches.append({
                    "job_id":   meta.get("job_id", f"job_{i}"),
                    "score":    round(score * 100, 1),  # Percentage
                    "company":  meta.get("company", "Unknown"),
                    "title":    meta.get("title", ""),
                    "metadata": meta,
                })

        return sorted(matches, key=lambda x: x["score"], reverse=True)

    def find_similar_jds(self, jd_text: str, top_k: int = 5) -> list[dict]:
        """
        Ek JD ke similar JDs dhundo — deduplication ke liye.
        Same company ki similar postings detect karo.
        """
        results = self.jd_collection.query(
            query_texts=[jd_text],
            n_results=min(top_k + 1, self.jd_collection.count() or 1),
            include=["metadatas", "distances"]
        )
        similar = []
        for dist, meta in zip(results["distances"][0], results["metadatas"][0]):
            score = 1 - dist
            if score > 0.9:   # 90%+ similar = probable duplicate
                similar.append({"score": score, **meta})
        return similar

    # ── Utility ───────────────────────────────
    def get_stats(self) -> dict:
        """Dashboard ke liye vector store stats."""
        return {
            "cv_count":    self.cv_collection.count(),
            "jd_count":    self.jd_collection.count(),
            "persist_path": os.getenv("CHROMA_PATH", CHROMA_PERSIST_PATH),
        }

    def delete_user_data(self, user_id: str) -> None:
        """GDPR compliance — user ka data delete karo."""
        try:
            self.cv_collection.delete(ids=[f"cv_{user_id}"])
            logger.info(f"Deleted CV for user: {user_id}")
        except Exception as e:
            logger.warning(f"Delete failed (may not exist): {e}")
