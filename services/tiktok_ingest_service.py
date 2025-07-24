import uuid
from datetime import datetime, timezone
from config.firebase_config import get_firestore_db

class TikTokIngestService:
    @staticmethod
    def mock_create_job(url, owner_uid=None):
        # Generate IDs
        job_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        status = "QUEUED"
        # Seed Firestore job doc if Firestore is available
        db = get_firestore_db()
        if db and owner_uid:
            now = datetime.now(timezone.utc).isoformat()
            job_doc = {
                "status": status,
                "createdAt": now,
                "owner_uid": owner_uid,
                "recipe_id": recipe_id,
                "url": url
            }
            db.collection("ingest_jobs").document(job_id).set(job_doc)
        return job_id, recipe_id, status

    @staticmethod
    def mock_get_job_status(job_id):
        db = get_firestore_db()
        if db:
            doc = db.collection("ingest_jobs").document(job_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "status": data.get("status", "QUEUED"),
                    "title": data.get("title"),
                    "transcript": data.get("transcript"),
                    "error_code": data.get("error_code")
                }
        # Fallback mock
        return {
            "status": "QUEUED",
            "title": None,
            "transcript": None,
            "error_code": None
        } 