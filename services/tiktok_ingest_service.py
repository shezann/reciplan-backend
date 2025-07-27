import uuid
import numpy as np
import json
from datetime import datetime, timezone
from config.firebase_config import get_firestore_db
from errors import PipelineStatus


def extract_ai_reasoning_from_data(job_data):
    """Extract AI reasoning and OCR decision data from Firestore job document"""
    ai_data = {}
    
    # Extract data sufficiency analysis
    ai_data["data_sufficiency_analysis"] = job_data.get("data_sufficiency_analysis")
    
    # Determine if OCR was skipped based on status and other indicators
    status = job_data.get("status", "")
    ai_data["ocr_was_skipped"] = status == PipelineStatus.OCR_SKIPPED
    
    # Extract OCR decision information
    if ai_data["ocr_was_skipped"]:
        ai_data["ocr_skip_reason"] = job_data.get("ocr_skipped_reason")
        ai_data["ocr_confidence_score"] = job_data.get("confidence_score")
        ai_data["ocr_decision_factors"] = job_data.get("decision_factors")
        ai_data["estimated_completeness"] = job_data.get("estimated_completeness")
    else:
        # OCR was run - extract reasoning for why it was needed
        ai_data["ocr_skip_reason"] = job_data.get("ocr_required_reason")
        ai_data["ocr_confidence_score"] = job_data.get("confidence_score")
        ai_data["ocr_decision_factors"] = job_data.get("decision_factors")
        ai_data["estimated_completeness"] = job_data.get("estimated_completeness")
    
    # Extract pipeline performance data
    ai_data["pipeline_performance"] = {
        "ocr_was_skipped": ai_data["ocr_was_skipped"],
        "confidence_score": ai_data["ocr_confidence_score"],
        "total_duration_seconds": job_data.get("total_duration_seconds"),
        "pipeline_completed_at": job_data.get("pipeline_completed_at")
    }
    
    # Clean up None values
    ai_data = {k: v for k, v in ai_data.items() if v is not None}
    
    return ai_data


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
                # Extract AI reasoning data from status updates
                ai_reasoning_data = extract_ai_reasoning_from_data(data)
                
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
                    "recipe_id": data.get("recipe_id"),
                    
                    # AI reasoning and OCR decision data
                    "data_sufficiency_analysis": ai_reasoning_data.get("data_sufficiency_analysis"),
                    "ocr_was_skipped": ai_reasoning_data.get("ocr_was_skipped"),
                    "ocr_skip_reason": ai_reasoning_data.get("ocr_skip_reason"),
                    "ocr_confidence_score": ai_reasoning_data.get("ocr_confidence_score"),
                    "ocr_decision_factors": ai_reasoning_data.get("ocr_decision_factors"),
                    "estimated_completeness": ai_reasoning_data.get("estimated_completeness"),
                    
                    # Pipeline performance metrics
                    "pipeline_performance": ai_reasoning_data.get("pipeline_performance"),
                    "total_duration_seconds": data.get("total_duration_seconds")
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
            "recipe_id": None,
            
            # AI reasoning fallback values
            "data_sufficiency_analysis": None,
            "ocr_was_skipped": None,
            "ocr_skip_reason": None,
            "ocr_confidence_score": None,
            "ocr_decision_factors": None,
            "estimated_completeness": None,
            "pipeline_performance": None,
            "total_duration_seconds": None
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