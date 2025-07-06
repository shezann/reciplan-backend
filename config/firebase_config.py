"""
Firebase configuration and initialization
"""
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Global Firebase app instance
_firebase_app = None
_firestore_db = None
_firebase_initialized = False

def get_firebase_app():
    """Get the Firebase app instance, initializing if needed"""
    global _firebase_app, _firebase_initialized
    
    if _firebase_app is None and not _firebase_initialized:
        try:
            # Check if we have a service account file path
            service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
            
            if service_account_path and os.path.exists(service_account_path):
                # Initialize with service account file
                cred = credentials.Certificate(service_account_path)
                _firebase_app = firebase_admin.initialize_app(cred)
            else:
                # Check for service account key in environment variable
                service_account_key = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
                
                if service_account_key:
                    # Parse JSON from environment variable
                    try:
                        service_account_info = json.loads(service_account_key)
                        cred = credentials.Certificate(service_account_info)
                        _firebase_app = firebase_admin.initialize_app(cred)
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON in FIREBASE_SERVICE_ACCOUNT_KEY")
                else:
                    # Use default credentials (for Cloud Run, App Engine, etc.)
                    cred = credentials.ApplicationDefault()
                    _firebase_app = firebase_admin.initialize_app(cred)
            
            _firebase_initialized = True
        except Exception as e:
            print(f"❌ Firebase initialization failed: {e}")
            _firebase_initialized = True  # Mark as attempted to avoid retry
            return None
    
    return _firebase_app

def get_firestore_db():
    """Get the Firestore database instance"""
    global _firestore_db
    
    if _firestore_db is None:
        # Try to get Firebase app
        app = get_firebase_app()
        if app is None:
            print("⚠️  Warning: Firebase not initialized, Firestore unavailable")
            return None
        
        try:
            _firestore_db = firestore.client()
        except Exception as e:
            print(f"❌ Firestore client initialization failed: {e}")
            return None
    
    return _firestore_db

def initialize_firebase():
    """Initialize Firebase (called from app startup)"""
    try:
        app = get_firebase_app()
        if app is None:
            print("⚠️  Firebase not configured - authentication features will be limited")
            return False
        
        db = get_firestore_db()
        if db is None:
            print("⚠️  Firestore not available - database features will be limited")
            return False
        
        print("✅ Firebase initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return False

def is_firebase_available():
    """Check if Firebase is available and configured"""
    return _firebase_app is not None and _firestore_db is not None 