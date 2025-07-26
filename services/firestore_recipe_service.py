from typing import Dict, Any, Optional
from datetime import datetime, timezone
from google.cloud import firestore

class FirestoreRecipeService:
    """Service for handling Firestore recipe document updates"""
    
    def __init__(self, db: firestore.Client):
        """Initialize with Firestore client"""
        self.db = db
    
    def update_recipe_with_llm_results(self, 
                                     job_id: str, 
                                     recipe_id: str, 
                                     recipe_json: Dict[str, Any],
                                     llm_metadata: Dict[str, Any],
                                     parse_error: Optional[str] = None) -> bool:
        """
        Update both ingest_jobs and recipes collections with LLM results
        
        Args:
            job_id: The ingest job document ID
            recipe_id: The recipe document ID
            recipe_json: The structured recipe data from LLM
            llm_metadata: Metadata about the LLM processing
            parse_error: Optional parse error message
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            
            # Prepare comprehensive update data
            update_data = {
                "status": "DRAFT_PARSED_WITH_ERRORS" if parse_error else "DRAFT_PARSED",
                "updatedAt": now_str,
                "recipe_json": recipe_json,
                "has_parse_errors": parse_error is not None
            }
            
            # Add LLM metadata
            update_data.update(llm_metadata)
            
            # Add parse error if present
            if parse_error:
                update_data["parse_errors"] = parse_error
            
            # Add recipe statistics for quick access
            if recipe_json:
                update_data["recipe_stats"] = self._extract_recipe_stats(recipe_json)
            
            # Update both collections
            success = self._update_both_collections(job_id, recipe_id, update_data)
            
            if success:
                print(f"[FirestoreRecipeService] Successfully updated documents for job {job_id}")
            else:
                print(f"[FirestoreRecipeService] Failed to update documents for job {job_id}")
            
            return success
            
        except Exception as e:
            print(f"[FirestoreRecipeService] Error updating recipe with LLM results: {e}")
            return False
    
    def update_recipe_llm_failure(self, 
                                job_id: str, 
                                recipe_id: str, 
                                error_message: str) -> bool:
        """
        Update both collections with LLM failure status
        
        Args:
            job_id: The ingest job document ID
            recipe_id: The recipe document ID
            error_message: The error message from LLM processing
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            llm_failure_data = {
                "status": "LLM_FAILED",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "error_code": "LLM_FAILED",
                "llm_error_message": error_message,
                "llm_processing_completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            success = self._update_both_collections(job_id, recipe_id, llm_failure_data)
            
            if success:
                print(f"[FirestoreRecipeService] Successfully updated documents with LLM failure for job {job_id}")
            else:
                print(f"[FirestoreRecipeService] Failed to update documents with LLM failure for job {job_id}")
            
            return success
            
        except Exception as e:
            print(f"[FirestoreRecipeService] Error updating LLM failure: {e}")
            return False
    
    def _extract_recipe_stats(self, recipe_json: Dict[str, Any]) -> Dict[str, Any]:
        """Extract statistics from recipe JSON for quick access"""
        return {
            "ingredients_count": len(recipe_json.get("ingredients", [])),
            "instructions_count": len(recipe_json.get("instructions", [])),
            "has_prep_time": recipe_json.get("prep_time") is not None,
            "has_cook_time": recipe_json.get("cook_time") is not None,
            "has_servings": recipe_json.get("servings") is not None,
            "has_difficulty": recipe_json.get("difficulty") is not None,
            "has_nutrition": bool(recipe_json.get("nutrition", {})),
            "has_tags": bool(recipe_json.get("tags", [])),
            "has_description": bool(recipe_json.get("description", ""))
        }
    
    def _update_both_collections(self, 
                               job_id: str, 
                               recipe_id: str, 
                               update_data: Dict[str, Any]) -> bool:
        """
        Update both ingest_jobs and recipes collections with error handling
        
        Args:
            job_id: The ingest job document ID
            recipe_id: The recipe document ID
            update_data: The data to update
            
        Returns:
            True if both updates succeeded, False otherwise
        """
        try:
            # Update ingest_jobs collection
            self.db.collection("ingest_jobs").document(job_id).update(update_data)
            
            # Update recipes collection
            self.db.collection("recipes").document(recipe_id).update(update_data)
            
            return True
            
        except Exception as e:
            print(f"[FirestoreRecipeService] Firestore update error: {e}")
            
            # Try minimal update as fallback
            try:
                minimal_update = {
                    "status": update_data.get("status", "UNKNOWN"),
                    "updatedAt": update_data.get("updatedAt"),
                    "firestore_update_error": str(e)
                }
                
                # Add recipe_json if available
                if "recipe_json" in update_data:
                    minimal_update["recipe_json"] = update_data["recipe_json"]
                
                self.db.collection("ingest_jobs").document(job_id).update(minimal_update)
                self.db.collection("recipes").document(recipe_id).update(minimal_update)
                
                print(f"[FirestoreRecipeService] Applied minimal Firestore update after error")
                return True
                
            except Exception as fallback_error:
                print(f"[FirestoreRecipeService] Fallback Firestore update also failed: {fallback_error}")
                return False
    
    def get_recipe_document(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a recipe document by ID
        
        Args:
            recipe_id: The recipe document ID
            
        Returns:
            Recipe document data or None if not found
        """
        try:
            doc_ref = self.db.collection("recipes").document(recipe_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
                
        except Exception as e:
            print(f"[FirestoreRecipeService] Error getting recipe document: {e}")
            return None
    
    def get_job_document(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an ingest job document by ID
        
        Args:
            job_id: The ingest job document ID
            
        Returns:
            Job document data or None if not found
        """
        try:
            doc_ref = self.db.collection("ingest_jobs").document(job_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
                
        except Exception as e:
            print(f"[FirestoreRecipeService] Error getting job document: {e}")
            return None 