"""
firebase_config.py — Firebase Initialization
"""
import os
import logging
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth

logger = logging.getLogger(__name__)

@st.cache_resource
def init_firebase():
    if firebase_admin._apps:
        return firestore.client()

    try:
        cred = _get_credentials()
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase connected")
        return firestore.client()

    except Exception as e:
        logger.error(f"Firebase error: {e}")
        st.error(f"⚠️ Firebase error: {e}")
        raise

def _get_credentials():
    """Try multiple credential sources"""

    # Option 1: Railway Environment Variables
    if os.getenv("FIREBASE_PRIVATE_KEY"):
        cred_dict = {
            "type": "service_account",
            "project_id":   os.getenv("FIREBASE_PROJECT_ID"),
            "private_key":  os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID", "key1"),
            "client_id":    os.getenv("FIREBASE_CLIENT_ID", ""),
            "auth_uri":     "https://accounts.google.com/o/oauth2/auth",
            "token_uri":    "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": ""
        }
        logger.info("Using Railway environment variables")
        return credentials.Certificate(cred_dict)

    # Option 2: Local JSON file
    elif os.path.exists("serviceAccountKey.json"):
        logger.info("Using serviceAccountKey.json")
        return credentials.Certificate("serviceAccountKey.json")

    # Option 3: Streamlit secrets
    elif hasattr(st, 'secrets') and "firebase" in st.secrets:
        logger.info("Using Streamlit secrets")
        return credentials.Certificate(dict(st.secrets["firebase"]))

    else:
        raise FileNotFoundError(
            "No Firebase credentials found!\n"
            "Set FIREBASE_PRIVATE_KEY, FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL in Railway Variables"
        )

def get_db():
    return init_firebase()
