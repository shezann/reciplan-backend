#!/usr/bin/env python3
"""
Migration script to add likes_count and last_liked_by fields to existing recipes
This migration is idempotent - it will skip recipes that already have the likes_count field
"""

import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from google.cloud.firestore_v1 import FieldFilter
from google.cloud import firestore

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.firebase_config import get_firestore_db, is_firebase_available


class AddLikesCountMigration:
    """Migration to add likes_count and last_liked_by fields to recipes"""
    
    def __init__(self):
        self.db = get_firestore_db()
        self.migration_name = "add_likes_count"
        self.migration_version = "1.0.0"
    
    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run the migration to add likes fields to existing recipes
        
        Args:
            dry_run: If True, only count recipes that would be updated without making changes
            
        Returns:
            Dictionary with migration results
        """
        if not self.db:
            raise Exception("Firestore database not available")
        
        print(f"[Migration] Starting {self.migration_name} migration (dry_run={dry_run})")
        
        # Track migration results
        results = {
            "migration_name": self.migration_name,
            "migration_version": self.migration_version,
            "dry_run": dry_run,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "recipes_processed": 0,
            "recipes_updated": 0,
            "recipes_skipped": 0,
            "errors": [],
            "completed_at": None,
            "success": False
        }
        
        try:
            # Get all recipes that don't have likes_count field
            recipes_collection = self.db.collection('recipes')
            
            # Firestore doesn't support "field not exists" queries directly
            # So we'll iterate through all recipes and check field existence
            all_recipes = recipes_collection.stream()
            
            batch_size = 500  # Firestore batch write limit
            current_batch = self.db.batch()
            batch_count = 0
            
            for recipe_doc in all_recipes:
                results["recipes_processed"] += 1
                recipe_data = recipe_doc.to_dict()
                
                # Check if likes_count already exists (idempotency)
                if "likes_count" in recipe_data:
                    results["recipes_skipped"] += 1
                    print(f"[Migration] Skipping recipe {recipe_doc.id} - likes_count already exists")
                    continue
                
                # Prepare update data
                update_data = {
                    "likes_count": 0,
                    "last_liked_by": None,
                    "updated_at": datetime.now(timezone.utc).isoformat() + 'Z'
                }
                
                if not dry_run:
                    # Add to batch
                    current_batch.update(recipe_doc.reference, update_data)
                    batch_count += 1
                    
                    # Commit batch when it reaches limit
                    if batch_count >= batch_size:
                        current_batch.commit()
                        print(f"[Migration] Committed batch of {batch_count} updates")
                        current_batch = self.db.batch()
                        batch_count = 0
                
                results["recipes_updated"] += 1
                
                if results["recipes_processed"] % 100 == 0:
                    print(f"[Migration] Processed {results['recipes_processed']} recipes...")
            
            # Commit remaining batch
            if not dry_run and batch_count > 0:
                current_batch.commit()
                print(f"[Migration] Committed final batch of {batch_count} updates")
            
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["success"] = True
            
            print(f"[Migration] Completed successfully!")
            print(f"  - Recipes processed: {results['recipes_processed']}")
            print(f"  - Recipes updated: {results['recipes_updated']}")
            print(f"  - Recipes skipped: {results['recipes_skipped']}")
            
            # Log migration to migrations collection
            if not dry_run:
                self._log_migration(results)
            
            return results
            
        except Exception as e:
            error_msg = f"Migration failed: {str(e)}"
            results["errors"].append(error_msg)
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            print(f"[Migration] ERROR: {error_msg}")
            raise e
    
    def _log_migration(self, results: Dict[str, Any]) -> None:
        """Log migration results to migrations collection for tracking"""
        try:
            migrations_ref = self.db.collection('migrations').document(self.migration_name)
            migrations_ref.set(results)
            print(f"[Migration] Logged migration results to migrations collection")
        except Exception as e:
            print(f"[Migration] WARNING: Failed to log migration: {e}")
    
    def rollback(self) -> Dict[str, Any]:
        """
        Rollback the migration by removing likes_count and last_liked_by fields
        WARNING: This will permanently remove like data
        """
        print(f"[Migration] Starting rollback for {self.migration_name}")
        
        results = {
            "migration_name": self.migration_name,
            "operation": "rollback",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "recipes_processed": 0,
            "recipes_updated": 0,
            "errors": [],
            "completed_at": None,
            "success": False
        }
        
        try:
            # Get all recipes that have likes_count field
            recipes_collection = self.db.collection('recipes')
            all_recipes = recipes_collection.stream()
            
            batch_size = 500
            current_batch = self.db.batch()
            batch_count = 0
            
            for recipe_doc in all_recipes:
                results["recipes_processed"] += 1
                recipe_data = recipe_doc.to_dict()
                
                # Check if likes_count exists
                if "likes_count" not in recipe_data:
                    continue
                
                # Remove likes fields
                update_data = {
                    "likes_count": firestore.DELETE_FIELD,
                    "last_liked_by": firestore.DELETE_FIELD,
                    "updated_at": datetime.now(timezone.utc).isoformat() + 'Z'
                }
                
                current_batch.update(recipe_doc.reference, update_data)
                batch_count += 1
                results["recipes_updated"] += 1
                
                # Commit batch when it reaches limit
                if batch_count >= batch_size:
                    current_batch.commit()
                    current_batch = self.db.batch()
                    batch_count = 0
            
            # Commit remaining batch
            if batch_count > 0:
                current_batch.commit()
            
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["success"] = True
            
            print(f"[Migration] Rollback completed successfully!")
            print(f"  - Recipes processed: {results['recipes_processed']}")
            print(f"  - Recipes updated: {results['recipes_updated']}")
            
            return results
            
        except Exception as e:
            error_msg = f"Rollback failed: {str(e)}"
            results["errors"].append(error_msg)
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            print(f"[Migration] ROLLBACK ERROR: {error_msg}")
            raise e


def main():
    """CLI interface for running the migration"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Add likes_count and last_liked_by fields to recipes')
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    
    args = parser.parse_args()
    
    if not is_firebase_available():
        print("ERROR: Firebase is not available. Check your configuration.")
        sys.exit(1)
    
    migration = AddLikesCountMigration()
    
    try:
        if args.rollback:
            results = migration.rollback()
        else:
            results = migration.run(dry_run=args.dry_run)
        
        if results["success"]:
            print(f"\n✅ Migration completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Migration failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Migration crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 