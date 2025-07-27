import uuid
import numpy as np
import json
from datetime import datetime, timezone
from config.firebase_config import get_firestore_db
from errors import PipelineStatus


def serialize_for_firestore(obj):
    """Recursively serialize objects to be Firestore-compatible"""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, 'tolist'):  # Handle array-like objects
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_firestore(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(k): serialize_for_firestore(v) for k, v in obj.items()}
    else:
        return str(obj)


def simplify_ocr_data(onscreen_text):
    """Simplify OCR data to only keep essential text information"""
    simplified = []
    
    for i, frame in enumerate(onscreen_text):
        if not isinstance(frame, dict) or 'text_blocks' not in frame:
            continue
            
        frame_texts = []
        for block in frame['text_blocks']:
            if isinstance(block, dict) and 'text' in block:
                text = str(block['text']).strip()
                if text:  # Only keep non-empty text
                    frame_texts.append(text)
        
        if frame_texts:  # Only add frames that have text
            simplified.append({
                'timestamp': float(frame.get('timestamp', 0)),
                'texts': frame_texts
            })
    
    # Limit the number of frames to prevent Firestore size issues
    return simplified[:20] if len(simplified) > 20 else simplified


class TikTokIngestService:
    @staticmethod
    def mock_create_job(url, owner_uid=None):
        """Create a new ingestion job with associated recipe document"""
        # Generate IDs
        job_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        status = PipelineStatus.QUEUED
        
        # Seed Firestore documents if available
        db = get_firestore_db()
        if db and owner_uid:
            now = datetime.now(timezone.utc).isoformat()
            
            # Create job document
            job_doc = {
                "status": status,
                "createdAt": now,
                "owner_uid": owner_uid,
                "recipe_id": recipe_id,
                "url": url
            }
            db.collection("ingest_jobs").document(job_id).set(job_doc)
            
            # Create stub recipe document
            recipe_doc = {
                "status": status,
                "createdAt": now,
                "owner_uid": owner_uid,
                "user_id": owner_uid  # Add user_id for frontend ownership validation
            }
            db.collection("recipes").document(recipe_id).set(recipe_doc)
            
        return job_id, recipe_id, status

    @staticmethod
    def mock_get_job_status(job_id):
        """Get job status from Firestore or return fallback"""
        db = get_firestore_db()
        if db:
            doc = db.collection("ingest_jobs").document(job_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "status": data.get("status", PipelineStatus.QUEUED),
                    "title": data.get("title"),
                    "transcript": data.get("transcript"),
                    "error_code": data.get("error_code"),
                    "recipe_json": data.get("recipe_json"),
                    "parse_errors": data.get("parse_errors"),
                    "llm_model_used": data.get("llm_model_used"),
                    "llm_processing_time_seconds": data.get("llm_processing_time_seconds"),
                    "llm_processing_completed_at": data.get("llm_processing_completed_at"),
                    "has_parse_errors": data.get("has_parse_errors"),
                    "recipe_stats": data.get("recipe_stats"),
                    "llm_error_message": data.get("llm_error_message"),
                    "recipe_id": data.get("recipe_id")
                }
        
        # Fallback response
        return {
            "status": PipelineStatus.QUEUED,
            "title": None,
            "transcript": None,
            "error_code": None,
            "recipe_json": None,
            "parse_errors": None,
            "llm_model_used": None,
            "llm_processing_time_seconds": None,
            "llm_processing_completed_at": None,
            "has_parse_errors": None,
            "recipe_stats": None,
            "llm_error_message": None,
            "recipe_id": None
        }

    @staticmethod
    def update_ocr_results(job_id: str, onscreen_text: list, ingredient_candidates: list):
        """Update job document with OCR results"""
        db = get_firestore_db()
        if not db:
            return
            
        try:
            # Simplify and serialize the OCR data
            simplified_onscreen_text = simplify_ocr_data(onscreen_text)
            safe_onscreen_text = serialize_for_firestore(simplified_onscreen_text)
            safe_ingredient_candidates = serialize_for_firestore(ingredient_candidates)
            
            # Prepare update data
            update_data = {
                "onscreen_text": safe_onscreen_text,
                "ingredient_candidates": safe_ingredient_candidates,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            
            # Update the document
            db.collection("ingest_jobs").document(job_id).update(update_data)
            print(f"[TikTokIngestService] Successfully updated OCR results for job {job_id}")
            
        except Exception as e:
            print(f"[TikTokIngestService] Error updating OCR results for job {job_id}: {e}")
            raise 