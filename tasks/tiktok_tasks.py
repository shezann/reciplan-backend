from tasks.celery_app import celery_app
from config.firebase_config import get_firestore_db
from datetime import datetime, timezone
import time

@celery_app.task(bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True)
def ingest_tiktok(self, job_id, url, owner_uid, recipe_id):
    db = get_firestore_db()
    try:
        # Update job status to IN_PROGRESS
        if db:
            now = datetime.now(timezone.utc).isoformat()
            db.collection("ingest_jobs").document(job_id).update({
                "status": "IN_PROGRESS",
                "updatedAt": now
            })
        # (Further processing will be implemented in later tasks)
        # Simulate possible transient error for demonstration
        # time.sleep(1)
        # raise Exception("Simulated transient error")
        return {"job_id": job_id, "status": "IN_PROGRESS"}
    except Exception as exc:
        # On final retry, mark job as FAILED
        if db:
            now = datetime.now(timezone.utc).isoformat()
            db.collection("ingest_jobs").document(job_id).update({
                "status": "FAILED",
                "updatedAt": now,
                "error_code": "INGEST_FAILED"
            })
        raise self.retry(exc=exc) 