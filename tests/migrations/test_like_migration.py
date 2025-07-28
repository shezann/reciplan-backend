#!/usr/bin/env python3
"""
Tests for the add_likes_count migration
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from datetime import datetime, timezone

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from firestore_migrations.add_likes_count import AddLikesCountMigration


class TestAddLikesCountMigration(unittest.TestCase):
    """Test cases for AddLikesCountMigration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.migration = AddLikesCountMigration()
        self.migration.db = self.mock_db
        
        # Sample recipe data
        self.recipe_without_likes = {
            "title": "Test Recipe",
            "description": "A test recipe",
            "ingredients": [{"name": "flour", "quantity": "2 cups"}],
            "instructions": ["Mix ingredients"],
            "user_id": "user123",
            "is_public": True,
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        self.recipe_with_likes = {
            **self.recipe_without_likes,
            "likes_count": 5,
            "last_liked_by": "user456"
        }
    
    def test_migration_init(self):
        """Test migration initialization"""
        migration = AddLikesCountMigration()
        self.assertEqual(migration.migration_name, "add_likes_count")
        self.assertEqual(migration.migration_version, "1.0.0")
    
    @patch('firestore_migrations.add_likes_count.get_firestore_db')
    def test_migration_no_database(self, mock_get_db):
        """Test migration fails gracefully when no database is available"""
        mock_get_db.return_value = None
        migration = AddLikesCountMigration()
        
        with self.assertRaises(Exception) as context:
            migration.run()
        
        self.assertIn("Firestore database not available", str(context.exception))
    
    def test_dry_run_mode(self):
        """Test dry run mode doesn't make actual changes"""
        # Mock recipe documents
        mock_doc1 = Mock()
        mock_doc1.id = "recipe1"
        mock_doc1.to_dict.return_value = self.recipe_without_likes
        
        mock_doc2 = Mock()
        mock_doc2.id = "recipe2"
        mock_doc2.to_dict.return_value = self.recipe_with_likes
        
        # Mock collection stream
        self.mock_db.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]
        
        # Run dry run
        results = self.migration.run(dry_run=True)
        
        # Verify results
        self.assertTrue(results["success"])
        self.assertTrue(results["dry_run"])
        self.assertEqual(results["recipes_processed"], 2)
        self.assertEqual(results["recipes_updated"], 1)  # Only recipe without likes
        self.assertEqual(results["recipes_skipped"], 1)  # Recipe with likes
        
        # Verify no batch operations were called
        self.mock_db.batch.assert_not_called()
    
    def test_migration_idempotency(self):
        """Test migration skips recipes that already have likes_count"""
        # Mock recipe documents
        mock_doc1 = Mock()
        mock_doc1.id = "recipe1"
        mock_doc1.to_dict.return_value = self.recipe_with_likes  # Already has likes
        
        mock_doc2 = Mock()
        mock_doc2.id = "recipe2"
        mock_doc2.to_dict.return_value = self.recipe_with_likes  # Already has likes
        
        # Mock collection stream
        self.mock_db.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]
        
        # Mock batch
        mock_batch = Mock()
        self.mock_db.batch.return_value = mock_batch
        
        # Run migration
        results = self.migration.run(dry_run=False)
        
        # Verify all recipes were skipped
        self.assertTrue(results["success"])
        self.assertEqual(results["recipes_processed"], 2)
        self.assertEqual(results["recipes_updated"], 0)
        self.assertEqual(results["recipes_skipped"], 2)
        
        # Verify no updates were made
        mock_batch.update.assert_not_called()
        mock_batch.commit.assert_not_called()
    
    def test_migration_updates_recipes_without_likes(self):
        """Test migration updates recipes that don't have likes_count"""
        # Mock recipe documents
        mock_doc1 = Mock()
        mock_doc1.id = "recipe1"
        mock_doc1.to_dict.return_value = self.recipe_without_likes
        mock_doc1.reference = Mock()
        
        mock_doc2 = Mock()
        mock_doc2.id = "recipe2" 
        mock_doc2.to_dict.return_value = self.recipe_without_likes
        mock_doc2.reference = Mock()
        
        # Mock collection stream
        self.mock_db.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]
        
        # Mock batch
        mock_batch = Mock()
        self.mock_db.batch.return_value = mock_batch
        
        # Run migration
        results = self.migration.run(dry_run=False)
        
        # Verify results
        self.assertTrue(results["success"])
        self.assertEqual(results["recipes_processed"], 2)
        self.assertEqual(results["recipes_updated"], 2)
        self.assertEqual(results["recipes_skipped"], 0)
        
        # Verify batch operations
        self.assertEqual(mock_batch.update.call_count, 2)
        mock_batch.commit.assert_called_once()  # One commit for both recipes
        
        # Verify update data structure
        update_calls = mock_batch.update.call_args_list
        for call in update_calls:
            _, update_data = call[0]  # Get the update data argument
            self.assertEqual(update_data["likes_count"], 0)
            self.assertIsNone(update_data["last_liked_by"])
            self.assertIn("updated_at", update_data)
    
    def test_migration_batch_processing(self):
        """Test migration handles large batches correctly"""
        # Create 1000 mock recipes to test batch processing
        mock_docs = []
        for i in range(1000):
            mock_doc = Mock()
            mock_doc.id = f"recipe{i}"
            mock_doc.to_dict.return_value = self.recipe_without_likes
            mock_doc.reference = Mock()
            mock_docs.append(mock_doc)
        
        # Mock collection stream
        self.mock_db.collection.return_value.stream.return_value = mock_docs
        
        # Mock batch
        mock_batch = Mock()
        self.mock_db.batch.return_value = mock_batch
        
        # Run migration
        results = self.migration.run(dry_run=False)
        
        # Verify results
        self.assertTrue(results["success"])
        self.assertEqual(results["recipes_processed"], 1000)
        self.assertEqual(results["recipes_updated"], 1000)
        
        # Verify batch commits (should be 2: one at 500, one final)
        self.assertEqual(mock_batch.commit.call_count, 2)
    
    def test_migration_logging(self):
        """Test migration logs results to migrations collection"""
        # Mock empty recipe stream
        self.mock_db.collection.return_value.stream.return_value = []
        
        # Mock migrations collection
        mock_migrations_ref = Mock()
        self.mock_db.collection.return_value.document.return_value = mock_migrations_ref
        
        # Run migration
        results = self.migration.run(dry_run=False)
        
        # Verify logging was called
        mock_migrations_ref.set.assert_called_once()
        logged_data = mock_migrations_ref.set.call_args[0][0]
        
        # Verify logged data structure
        self.assertEqual(logged_data["migration_name"], "add_likes_count")
        self.assertEqual(logged_data["migration_version"], "1.0.0")
        self.assertTrue(logged_data["success"])
    
    def test_migration_error_handling(self):
        """Test migration handles errors gracefully"""
        # Mock collection to raise an exception
        self.mock_db.collection.side_effect = Exception("Database connection failed")
        
        # Run migration and expect exception
        with self.assertRaises(Exception) as context:
            self.migration.run()
        
        self.assertIn("Database connection failed", str(context.exception))
    
    def test_rollback_functionality(self):
        """Test rollback removes likes fields"""
        # Mock recipe documents with likes
        mock_doc1 = Mock()
        mock_doc1.id = "recipe1"
        mock_doc1.to_dict.return_value = self.recipe_with_likes
        mock_doc1.reference = Mock()
        
        # Mock collection stream
        self.mock_db.collection.return_value.stream.return_value = [mock_doc1]
        
        # Mock batch
        mock_batch = Mock()
        self.mock_db.batch.return_value = mock_batch
        
        # Run rollback
        results = self.migration.rollback()
        
        # Verify results
        self.assertTrue(results["success"])
        self.assertEqual(results["recipes_processed"], 1)
        self.assertEqual(results["recipes_updated"], 1)
        
        # Verify batch operations called DELETE_FIELD
        mock_batch.update.assert_called_once()
        update_call_args = mock_batch.update.call_args[0]
        update_data = update_call_args[1]
        
        # Check that DELETE_FIELD was used (we can't easily test the exact value due to mocking)
        self.assertIn("likes_count", update_data)
        self.assertIn("last_liked_by", update_data)
        self.assertIn("updated_at", update_data)


class TestMigrationIntegration(unittest.TestCase):
    """Integration tests for migration with mocked Firestore"""
    
    @patch('firestore_migrations.add_likes_count.is_firebase_available')
    @patch('firestore_migrations.add_likes_count.get_firestore_db')
    def test_full_migration_workflow(self, mock_get_db, mock_is_available):
        """Test complete migration workflow from start to finish"""
        mock_is_available.return_value = True
        
        # Create a more realistic mock setup
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # Mock recipe without likes
        mock_doc = Mock()
        mock_doc.id = "test_recipe"
        mock_doc.to_dict.return_value = {
            "title": "Test Recipe",
            "user_id": "user123",
            "is_public": True
        }
        mock_doc.reference = Mock()
        
        # Mock collection operations
        mock_collection = Mock()
        mock_collection.stream.return_value = [mock_doc]
        mock_db.collection.return_value = mock_collection
        
        # Mock batch operations
        mock_batch = Mock()
        mock_db.batch.return_value = mock_batch
        
        # Mock migrations collection for logging
        mock_migrations_doc = Mock()
        mock_collection.document.return_value = mock_migrations_doc
        
        # Run migration
        migration = AddLikesCountMigration()
        results = migration.run(dry_run=False)
        
        # Verify successful execution
        self.assertTrue(results["success"])
        self.assertEqual(results["recipes_processed"], 1)
        self.assertEqual(results["recipes_updated"], 1)
        self.assertEqual(results["recipes_skipped"], 0)
        
        # Verify database operations
        mock_batch.update.assert_called_once()
        mock_batch.commit.assert_called_once()
        mock_migrations_doc.set.assert_called_once()


if __name__ == "__main__":
    unittest.main() 