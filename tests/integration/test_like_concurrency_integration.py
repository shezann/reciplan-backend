#!/usr/bin/env python3
"""
Integration tests for like service concurrency
Tests the actual service with mocked Firestore for concurrency validation
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.like_service import LikeService


class TestLikeConcurrencyIntegration(unittest.TestCase):
    """Integration tests for like service under concurrent load"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        # Create a shared state to simulate database consistency
        self.shared_state = {
            'recipes': {},  # recipe_id -> recipe_data
            'likes': {},    # (recipe_id, user_id) -> like_data
            'lock': threading.Lock()
        }
        
        # Initialize test recipe
        self.test_recipe_id = 'integration_recipe_123'
        self.shared_state['recipes'][self.test_recipe_id] = {
            'title': 'Integration Test Recipe',
            'user_id': 'recipe_owner',
            'is_public': True,
            'likes_count': 0,
            'last_liked_by': None,
            'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
        }
    
    @patch('services.like_service.get_firestore_db')
    def test_concurrent_likes_data_integrity(self, mock_get_db):
        """Test that concurrent likes maintain data integrity"""
        # Set up mock database with shared state
        mock_db = self._create_mock_db_with_shared_state()
        mock_get_db.return_value = mock_db
        
        # Create like service instance
        like_service = LikeService()
        
        num_users = 20
        recipe_id = self.test_recipe_id
        
        # Execute concurrent like operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(num_users):
                user_id = f'concurrent_user_{i}'
                future = executor.submit(like_service.toggle_like, recipe_id, user_id, True)
                futures.append((future, user_id))
            
            # Collect results
            results = []
            for future, user_id in futures:
                try:
                    result = future.result(timeout=10)
                    results.append((user_id, result))
                except Exception as e:
                    self.fail(f"Concurrent like failed for user {user_id}: {e}")
        
        # Verify all operations completed successfully
        self.assertEqual(len(results), num_users)
        
        # Verify data integrity in shared state
        with self.shared_state['lock']:
            recipe_data = self.shared_state['recipes'][recipe_id]
            actual_likes_count = recipe_data['likes_count']
            
            # Count actual likes in shared state
            likes_for_recipe = sum(1 for (r_id, u_id) in self.shared_state['likes'].keys() 
                                 if r_id == recipe_id)
            
            self.assertEqual(actual_likes_count, likes_for_recipe,
                           f"Recipe likes_count ({actual_likes_count}) should match actual likes ({likes_for_recipe})")
            self.assertEqual(actual_likes_count, num_users,
                           f"Should have exactly {num_users} likes")
        
        # Verify all users report being liked
        for user_id, result in results:
            self.assertIsNotNone(result, f"Result should not be None for user {user_id}")
            self.assertTrue(result['liked'], f"User {user_id} should show as liked")
            # likes_count may vary during execution but should be positive
            self.assertGreater(result['likes_count'], 0, f"likes_count should be > 0 for user {user_id}")
    
    @patch('services.like_service.get_firestore_db')
    def test_concurrent_like_unlike_same_user(self, mock_get_db):
        """Test concurrent like/unlike from same user (idempotency verification)"""
        # Set up mock database
        mock_db = self._create_mock_db_with_shared_state()
        mock_get_db.return_value = mock_db
        
        like_service = LikeService()
        recipe_id = self.test_recipe_id
        user_id = 'oscillating_user'
        
        # Execute alternating like/unlike operations
        num_operations = 50
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(num_operations):
                like_action = i % 2 == 0  # Alternate between like and unlike
                future = executor.submit(like_service.toggle_like, recipe_id, user_id, like_action)
                futures.append((future, like_action, i))
            
            # Collect results
            results = []
            for future, like_action, operation_num in futures:
                try:
                    result = future.result(timeout=10)
                    results.append((operation_num, like_action, result))
                except Exception as e:
                    self.fail(f"Operation {operation_num} ({'like' if like_action else 'unlike'}) failed: {e}")
        
        # Verify all operations completed
        self.assertEqual(len(results), num_operations)
        
        # Final state should be consistent
        with self.shared_state['lock']:
            recipe_data = self.shared_state['recipes'][recipe_id]
            final_likes_count = recipe_data['likes_count']
            
            # Check if user has a like document
            user_has_like = (recipe_id, user_id) in self.shared_state['likes']
            
            # Consistency check
            if user_has_like:
                self.assertEqual(final_likes_count, 1, "If user has like, count should be 1")
            else:
                self.assertEqual(final_likes_count, 0, "If user has no like, count should be 0")
        
        print(f"✅ Oscillation test completed: {num_operations} operations, "
              f"final likes_count: {final_likes_count}, user_has_like: {user_has_like}")
    
    def _create_mock_db_with_shared_state(self):
        """Create a mock Firestore database that uses shared state for consistency"""
        mock_db = Mock()
        
        def mock_transaction():
            """Create a mock transaction that operates on shared state"""
            transaction_mock = Mock()
            
            # The actual transaction decorator will call the decorated function
            # We need to intercept the toggle_like method to use our shared state
            original_toggle = self._create_shared_state_toggle_like()
            
            return transaction_mock
        
        mock_db.transaction = mock_transaction
        
        # Mock collection and document access
        def mock_collection(collection_name):
            collection_mock = Mock()
            
            def mock_document(doc_id):
                doc_mock = Mock()
                
                def mock_get(transaction=None):
                    doc_data_mock = Mock()
                    
                    if collection_name == 'recipes':
                        with self.shared_state['lock']:
                            if doc_id in self.shared_state['recipes']:
                                doc_data_mock.exists = True
                                doc_data_mock.to_dict.return_value = self.shared_state['recipes'][doc_id].copy()
                            else:
                                doc_data_mock.exists = False
                    
                    return doc_data_mock
                
                def mock_update(updates, transaction=None):
                    if collection_name == 'recipes':
                        with self.shared_state['lock']:
                            if doc_id in self.shared_state['recipes']:
                                self.shared_state['recipes'][doc_id].update(updates)
                
                def mock_subcollection(subcoll_name):
                    subcoll_mock = Mock()
                    
                    def mock_subdoc(subdoc_id):
                        subdoc_mock = Mock()
                        
                        def mock_subget(transaction=None):
                            subdoc_data_mock = Mock()
                            
                            if subcoll_name == 'likes':
                                with self.shared_state['lock']:
                                    key = (doc_id, subdoc_id)  # (recipe_id, user_id)
                                    subdoc_data_mock.exists = key in self.shared_state['likes']
                                    if subdoc_data_mock.exists:
                                        subdoc_data_mock.to_dict.return_value = self.shared_state['likes'][key].copy()
                            
                            return subdoc_data_mock
                        
                        def mock_subset(data, transaction=None):
                            if subcoll_name == 'likes':
                                with self.shared_state['lock']:
                                    key = (doc_id, subdoc_id)
                                    self.shared_state['likes'][key] = data
                        
                        def mock_subdelete(transaction=None):
                            if subcoll_name == 'likes':
                                with self.shared_state['lock']:
                                    key = (doc_id, subdoc_id)
                                    self.shared_state['likes'].pop(key, None)
                        
                        subdoc_mock.get = mock_subget
                        subdoc_mock.set = mock_subset
                        subdoc_mock.delete = mock_subdelete
                        return subdoc_mock
                    
                    subcoll_mock.document = mock_subdoc
                    return subcoll_mock
                
                doc_mock.get = mock_get
                doc_mock.update = mock_update
                doc_mock.collection = mock_subcollection
                return doc_mock
            
            collection_mock.document = mock_document
            return collection_mock
        
        mock_db.collection = mock_collection
        return mock_db
    
    def _create_shared_state_toggle_like(self):
        """Create a toggle_like function that operates on shared state"""
        def toggle_like_with_shared_state(recipe_id, user_id, like):
            with self.shared_state['lock']:
                # Check recipe exists
                if recipe_id not in self.shared_state['recipes']:
                    return None
                
                recipe_data = self.shared_state['recipes'][recipe_id]
                
                # Check permissions
                if not recipe_data.get('is_public', False) and recipe_data.get('user_id') != user_id:
                    raise ValueError("Cannot like a private recipe you don't own")
                
                # Current state
                like_key = (recipe_id, user_id)
                currently_liked = like_key in self.shared_state['likes']
                current_count = recipe_data['likes_count']
                
                timestamp = datetime.now(timezone.utc)
                
                if like and not currently_liked:
                    # Like the recipe
                    self.shared_state['likes'][like_key] = {
                        'user_id': user_id,
                        'recipe_id': recipe_id,
                        'created_at': timestamp.isoformat() + 'Z'
                    }
                    new_count = current_count + 1
                    recipe_data['likes_count'] = new_count
                    recipe_data['last_liked_by'] = user_id
                    recipe_data['updated_at'] = timestamp.isoformat() + 'Z'
                    
                    return {
                        'liked': True,
                        'likes_count': new_count,
                        'timestamp': timestamp
                    }
                
                elif not like and currently_liked:
                    # Unlike the recipe
                    del self.shared_state['likes'][like_key]
                    new_count = max(0, current_count - 1)
                    recipe_data['likes_count'] = new_count
                    if new_count == 0:
                        recipe_data['last_liked_by'] = None
                    recipe_data['updated_at'] = timestamp.isoformat() + 'Z'
                    
                    return {
                        'liked': False,
                        'likes_count': new_count,
                        'timestamp': timestamp
                    }
                
                else:
                    # No change (idempotent)
                    return {
                        'liked': currently_liked,
                        'likes_count': current_count,
                        'timestamp': timestamp
                    }
        
        return toggle_like_with_shared_state


if __name__ == "__main__":
    unittest.main(verbosity=2) 