import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class FirebaseConfig:
    """Firebase configuration and initialization"""
    
    def __init__(self):
        self.app = None
        self.db = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if already initialized
            if firebase_admin._apps:
                self.app = firebase_admin.get_app()
            else:
                # Initialize from service account key file
                service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
                
                if service_account_path and os.path.exists(service_account_path):
                    # Initialize with service account file
                    cred = credentials.Certificate(service_account_path)
                    self.app = firebase_admin.initialize_app(cred)
                else:
                    # Initialize with service account key from environment variable
                    service_account_key = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
                    
                    if service_account_key:
                        # Parse the JSON key from environment variable
                        service_account_info = json.loads(service_account_key)
                        cred = credentials.Certificate(service_account_info)
                        self.app = firebase_admin.initialize_app(cred)
                    else:
                        # Initialize with default credentials (for deployment)
                        cred = credentials.ApplicationDefault()
                        self.app = firebase_admin.initialize_app(cred)
            
            # Initialize Firestore client
            self.db = firestore.client()
            print("Firebase initialized successfully")
            
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            raise
    
    def get_db(self):
        """Get Firestore database instance"""
        if self.db is None:
            raise Exception("Firebase not initialized properly")
        return self.db

# Global Firebase instance
firebase_config = FirebaseConfig() 