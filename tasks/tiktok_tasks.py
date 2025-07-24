from tasks.celery_app import celery_app
from config.firebase_config import get_firestore_db
from datetime import datetime, timezone
import time
from utils.media_downloader import download_video, VideoUnavailableError, temp_job_dir
from utils.audio_extractor import extract_audio, AudioExtractionError

@celery_app.task(bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True)
def ingest_tiktok(self, job_id, url, owner_uid, recipe_id):
    db = get_firestore_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        # Update job status to DOWNLOADING
        if db:
            db.collection("ingest_jobs").document(job_id).update({
                "status": "DOWNLOADING",
                "updatedAt": now
            })
        with temp_job_dir() as job_dir:
            # Download video
            try:
                video_path = download_video(url, output_dir=job_dir)
            except VideoUnavailableError as e:
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "FAILED",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "error_code": "VIDEO_UNAVAILABLE"
                    })
                raise self.retry(exc=e)
            # Update job status to EXTRACTING
            if db:
                db.collection("ingest_jobs").document(job_id).update({
                    "status": "EXTRACTING",
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                })
            # Extract audio
            try:
                audio_path = extract_audio(video_path, output_dir=job_dir)
            except AudioExtractionError as e:
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "FAILED",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "error_code": "AUDIO_EXTRACTION_FAILED"
                    })
                raise self.retry(exc=e)
        # (Further processing will be implemented in later tasks)
        return {"job_id": job_id, "status": "EXTRACTED"}
    except Exception as exc:
        # On final retry, mark job as FAILED
        if db:
            db.collection("ingest_jobs").document(job_id).update({
                "status": "FAILED",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "error_code": "INGEST_FAILED"
            })
        raise self.retry(exc=exc) 