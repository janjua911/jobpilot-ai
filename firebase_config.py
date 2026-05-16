"""
firebase_config.py — Firebase Initialization with Auth
"""
import os
import logging
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth

logger = logging.getLogger(__name__)


@st.cache_resource
def init_firebase():
    """Firebase initialize karo with anonymous auth"""
    
    if firebase_admin._apps:
        return firestore.client()
    
    try:
        # Load credentials
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
        elif "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
        else:
            raise FileNotFoundError("serviceAccountKey.json not found")
        
        firebase_admin.initialize_app(cred)
        
        # Create anonymous user for testing
        _setup_anonymous_user()
        
        logger.info("✅ Firebase Firestore connected")
        return firestore.client()
        
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        st.error(f"⚠️ Firebase error: {e}")
        raise


def _setup_anonymous_user():
    """Create or get anonymous user for testing"""
    try:
        # Check if anonymous user exists
        user = auth.get_user_by_email("anonymous@jobpilot.local")
    except:
        try:
            # Create anonymous user
            user = auth.create_user(
                email="anonymous@jobpilot.local",
                password="anonymous123",
                display_name="Anonymous User"
            )
            logger.info("Anonymous user created")
        except Exception as e:
            logger.warning(f"Could not create anonymous user: {e}")


def get_db():
    return init_firebase()