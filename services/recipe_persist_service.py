#!/usr/bin/env python3
"""
Service for persisting recipe data from ingest_jobs to recipes collection
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from firebase_admin import firestore

from config.firebase_config import get_firestore_db


class RecipePersistService:
    """Service for persisting recipe data to Firestore recipes collection"""
    
    def __init__(self):
        self.db = get_firestore_db()
    
    def save_recipe(self, 
                   recipe_json: Dict[str, Any], 
                   owner_uid: str,
                   source_url: str = "",
                   original_job_id: str = "") -> Optional[str]:
        """
        Save recipe_json to recipes collection and return recipe_id
        
        Args:
            recipe_json: The structured recipe data from LLM
            owner_uid: User ID who owns the recipe
            source_url: Original TikTok URL
            original_job_id: Reference to the ingest job
            
        Returns:
            recipe_id if successful, None if failed
        """
        if not self.db:
            print("[RecipePersistService] No Firestore connection available")
            return None
        
        try:
            # Generate recipe ID with prefix
            recipe_id = f"rec_{str(uuid.uuid4())}"
            now = datetime.now(timezone.utc).isoformat()
            
            # Prepare recipe document
            recipe_doc = {
                "recipe_json": recipe_json,
                "owner_uid": owner_uid,
                "createdAt": now,
                "updatedAt": now,
                "source_url": source_url,
                "original_job_id": original_job_id,
                "status": "ACTIVE"  # Recipe is ready for use
            }
            
            print(f"[RecipePersistService] Creating recipe document: {recipe_id}")
            print(f"[RecipePersistService] Recipe title: {recipe_json.get('title', 'Unknown')}")
            print(f"[RecipePersistService] Owner: {owner_uid}")
            
            # Write to recipes collection
            self.db.collection("recipes").document(recipe_id).set(recipe_doc)
            
            print(f"[RecipePersistService] Successfully created recipe: {recipe_id}")
            return recipe_id
            
        except Exception as e:
            print(f"[RecipePersistService] Error saving recipe: {e}")
            return None
    
    def update_job_with_recipe_id(self, job_id: str, recipe_id: str) -> bool:
        """
        Update the ingest job with the recipe_id reference
        
        Args:
            job_id: The ingest job document ID
            recipe_id: The recipe document ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db:
            print("[RecipePersistService] No Firestore connection available")
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            update_data = {
                "status": "COMPLETED",
                "recipe_id": recipe_id,
                "updatedAt": now
            }
            
            print(f"[RecipePersistService] Updating job {job_id} with recipe_id: {recipe_id}")
            
            # Update ingest_jobs collection
            self.db.collection("ingest_jobs").document(job_id).update(update_data)
            
            print(f"[RecipePersistService] Successfully updated job {job_id}")
            return True
            
        except Exception as e:
            print(f"[RecipePersistService] Error updating job: {e}")
            return False
    
    def save_recipe_and_update_job(self, 
                                 recipe_json: Dict[str, Any],
                                 job_id: str,
                                 owner_uid: str,
                                 source_url: str = "") -> Optional[str]:
        """
        Complete workflow: save recipe and update job status
        
        Args:
            recipe_json: The structured recipe data from LLM
            job_id: The ingest job document ID
            owner_uid: User ID who owns the recipe
            source_url: Original TikTok URL
            
        Returns:
            recipe_id if successful, None if failed
        """
        print(f"[RecipePersistService] Starting recipe persistence workflow for job: {job_id}")
        
        # Step 1: Save recipe to recipes collection
        recipe_id = self.save_recipe(
            recipe_json=recipe_json,
            owner_uid=owner_uid,
            source_url=source_url,
            original_job_id=job_id
        )
        
        if not recipe_id:
            print(f"[RecipePersistService] Failed to save recipe for job {job_id}")
            return None
        
        # Step 2: Update job with recipe_id
        success = self.update_job_with_recipe_id(job_id, recipe_id)
        
        if not success:
            print(f"[RecipePersistService] Failed to update job {job_id} with recipe_id {recipe_id}")
            # Note: We could delete the recipe document here if job update fails
            # For now, we'll leave it and let the job update be retried
            return None
        
        print(f"[RecipePersistService] Recipe persistence workflow completed successfully")
        print(f"[RecipePersistService] Job {job_id} -> Recipe {recipe_id}")
        
        return recipe_id
    
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a recipe document by ID
        
        Args:
            recipe_id: The recipe document ID
            
        Returns:
            Recipe document data if found, None otherwise
        """
        if not self.db:
            print("[RecipePersistService] No Firestore connection available")
            return None
        
        try:
            doc = self.db.collection("recipes").document(recipe_id).get()
            if doc.exists:
                return doc.to_dict()
            else:
                print(f"[RecipePersistService] Recipe {recipe_id} not found")
                return None
        except Exception as e:
            print(f"[RecipePersistService] Error retrieving recipe {recipe_id}: {e}")
            return None 