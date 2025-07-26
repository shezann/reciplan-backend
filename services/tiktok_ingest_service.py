import uuid
import numpy as np
import json
from datetime import datetime, timezone
from config.firebase_config import get_firestore_db

def deep_serialize(obj):
    """Recursively serialize objects to be Firestore-compatible"""
    try:
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'tolist'):  # Handle other array-like objects
            return obj.tolist()
        elif isinstance(obj, (list, tuple)):
            return [deep_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(k): deep_serialize(v) for k, v in obj.items()}
        elif hasattr(obj, '__dict__'):  # Handle custom objects
            return str(obj)
        else:
            return str(obj)
    except Exception as e:
        print(f"[DEBUG] Error serializing object {type(obj)}: {e}")
        return str(obj)

def simplify_ocr_data(onscreen_text):
    """Simplify OCR data to only keep essential text information"""
    print(f"[DEBUG] simplify_ocr_data input: {len(onscreen_text)} frames")
    simplified = []
    
    for i, frame in enumerate(onscreen_text):
        print(f"[DEBUG] Processing frame {i}: {type(frame)}")
        if not isinstance(frame, dict) or 'text_blocks' not in frame:
            print(f"[DEBUG] Skipping frame {i}: not a dict or no text_blocks")
            continue
            
        frame_texts = []
        print(f"[DEBUG] Frame {i} has {len(frame['text_blocks'])} text blocks")
        for j, block in enumerate(frame['text_blocks']):
            print(f"[DEBUG] Processing block {j}: {type(block)}")
            if isinstance(block, dict) and 'text' in block:
                text = str(block['text']).strip()
                print(f"[DEBUG] Block {j} text: '{text}'")
                if text and len(text) > 0:  # Only keep non-empty text
                    frame_texts.append(text)
                    print(f"[DEBUG] Added text: '{text}'")
                else:
                    print(f"[DEBUG] Skipped empty text")
            else:
                print(f"[DEBUG] Block {j} is not a dict or has no text key")
        
        if frame_texts:  # Only add frames that have text
            simplified.append({
                'timestamp': float(frame.get('timestamp', 0)),
                'texts': frame_texts
            })
            print(f"[DEBUG] Added frame {i} with {len(frame_texts)} texts")
        else:
            print(f"[DEBUG] No texts in frame {i}")
    
    # Limit the number of frames to prevent Firestore issues
    if len(simplified) > 20:
        simplified = simplified[:20]
    
    print(f"[DEBUG] simplify_ocr_data output: {len(simplified)} frames")
    return simplified

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
            # Create stub recipe doc to avoid NotFound error
            recipe_doc = {
                "status": status,
                "createdAt": now,
                "owner_uid": owner_uid
            }
            db.collection("recipes").document(recipe_id).set(recipe_doc)
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
                    "error_code": data.get("error_code"),
                    # New LLM-related fields
                    "recipe_json": data.get("recipe_json"),
                    "parse_errors": data.get("parse_errors"),
                    "llm_model_used": data.get("llm_model_used"),
                    "llm_processing_time_seconds": data.get("llm_processing_time_seconds"),
                    "llm_processing_completed_at": data.get("llm_processing_completed_at"),
                    "has_parse_errors": data.get("has_parse_errors"),
                    "recipe_stats": data.get("recipe_stats"),
                    "llm_error_message": data.get("llm_error_message"),
                    # Recipe persistence fields
                    "recipe_id": data.get("recipe_id")
                }
        # Fallback mock
        return {
            "status": "QUEUED",
            "title": None,
            "transcript": None,
            "error_code": None,
            # New LLM-related fields
            "recipe_json": None,
            "parse_errors": None,
            "llm_model_used": None,
            "llm_processing_time_seconds": None,
            "llm_processing_completed_at": None,
            "has_parse_errors": None,
            "recipe_stats": None,
            "llm_error_message": None,
            # Recipe persistence fields
            "recipe_id": None
        }

    @staticmethod
    def update_ocr_results(job_id: str, onscreen_text: list, ingredient_candidates: list):
        db = get_firestore_db()
        if db:
            try:
                print(f"[DEBUG] Raw onscreen_text type: {type(onscreen_text)}")
                print(f"[DEBUG] Raw onscreen_text length: {len(onscreen_text) if onscreen_text else 0}")
                
                # Simplify the OCR data to remove problematic fields
                simplified_onscreen_text = simplify_ocr_data(onscreen_text)
                print(f"[DEBUG] Simplified onscreen_text length: {len(simplified_onscreen_text)}")
                
                # Ensure all nested fields are Firestore-compatible
                safe_onscreen_text = deep_serialize(simplified_onscreen_text)
                safe_ingredient_candidates = deep_serialize(ingredient_candidates)
                
                print(f"[DEBUG] Serialized onscreen_text type: {type(safe_onscreen_text)}")
                print(f"[DEBUG] Serialized ingredient_candidates type: {type(safe_ingredient_candidates)}")
                
                # Test if the data can be JSON serialized (Firestore requirement)
                test_data = {
                    "onscreen_text": safe_onscreen_text,
                    "ingredient_candidates": safe_ingredient_candidates,
                }
                
                print(f"[DEBUG] Testing JSON serialization...")
                json_str = json.dumps(test_data)  # This will fail if data isn't JSON serializable
                print(f"[DEBUG] JSON serialization successful, length: {len(json_str)}")
                
                update = {
                    "onscreen_text": safe_onscreen_text,
                    "ingredient_candidates": safe_ingredient_candidates,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
                print("[DEBUG] Final Firestore update payload:")
                print(f"[DEBUG] - onscreen_text: {type(update['onscreen_text'])} with {len(update['onscreen_text']) if update['onscreen_text'] else 0} items")
                print(f"[DEBUG] - ingredient_candidates: {type(update['ingredient_candidates'])} with {len(update['ingredient_candidates']) if update['ingredient_candidates'] else 0} items")
                
                db.collection("ingest_jobs").document(job_id).update(update)
                print("[DEBUG] Firestore update successful!")
                
            except Exception as e:
                print(f"[DEBUG] Error in update_ocr_results: {e}")
                print(f"[DEBUG] Error type: {type(e)}")
                print(f"[DEBUG] onscreen_text type: {type(onscreen_text)}")
                print(f"[DEBUG] ingredient_candidates type: {type(ingredient_candidates)}")
                if onscreen_text:
                    print(f"[DEBUG] onscreen_text sample: {onscreen_text[:2] if len(onscreen_text) > 1 else onscreen_text}")
                raise 