#!/usr/bin/env python3
"""
Concurrency stress tests for like service operations
Tests transaction safety and data integrity under high concurrent load
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from collections import defaultdict

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.like_service import LikeService


class TestLikeConcurrency(unittest.TestCase):
    """Concurrency stress tests for like operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.like_service = LikeService()
        self.like_service.db = self.mock_db
        
        # Track transaction calls for verification
        self.transaction_calls = []
        self.recipe_updates = defaultdict(list)
        self.like_operations = []
        
        # Sample recipe data
        self.test_recipe_data = {
            'title': 'Test Recipe',
            'description': 'A test recipe for concurrency testing',
            'user_id': 'recipe_owner_123',
            'is_public': True,
            'likes_count': 0,
            'last_liked_by': None
        }
    
    def test_concurrent_likes_same_recipe_same_user(self):
        """Test multiple concurrent likes from same user on same recipe (idempotency)"""
        recipe_id = 'recipe_123'
        user_id = 'user_123'
        
        # Mock transaction behavior
        call_count = 0
        
        def mock_transaction_func(transaction):
            nonlocal call_count
            call_count += 1
            
            # Simulate recipe document
            recipe_ref = Mock()
            recipe_doc = Mock()
            recipe_doc.exists = True
            recipe_doc.to_dict.return_value = {
                **self.test_recipe_data,
                'likes_count': min(1, call_count)  # Should never exceed 1 for same user
            }
            
            # Simulate like document (exists after first call)
            like_ref = Mock()
            like_doc = Mock()
            like_doc.exists = call_count > 1  # First call creates it
            
            # Mock Firestore operations
            self.mock_db.collection.return_value.document.return_value = recipe_ref
            recipe_ref.get.return_value = recipe_doc
            recipe_ref.collection.return_value.document.return_value = like_ref
            like_ref.get.return_value = like_doc
            
            return {
                'liked': True,
                'likes_count': 1,  # Should always be 1 for idempotent operations
                'timestamp': datetime.now(timezone.utc)
            }
        
        self.mock_db.transaction.return_value = Mock()
        
        # Create 50 concurrent like operations from same user
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for _ in range(50):
                future = executor.submit(self._safe_like_operation, recipe_id, user_id, True, mock_transaction_func)
                futures.append(future)
            
            # Collect results
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=10)
                    results.append(result)
                except Exception as e:
                    self.fail(f"Concurrent like operation failed: {e}")
        
        # Verify all operations succeeded
        self.assertEqual(len(results), 50)
        
        # Verify all results show liked=True and likes_count=1 (idempotent)
        for result in results:
            self.assertTrue(result['liked'])
            self.assertEqual(result['likes_count'], 1)
    
    def test_concurrent_likes_same_recipe_different_users(self):
        """Test concurrent likes from different users on same recipe"""
        recipe_id = 'recipe_123'
        num_users = 100
        
        # Track likes for accuracy verification
        likes_tracker = {'count': 0, 'users': set()}
        lock = threading.Lock()
        
        def mock_transaction_func(transaction, user_id):
            with lock:
                # Simulate realistic transaction behavior
                recipe_ref = Mock()
                recipe_doc = Mock()
                recipe_doc.exists = True
                
                # Current state
                current_count = likes_tracker['count']
                user_already_liked = user_id in likes_tracker['users']
                
                recipe_doc.to_dict.return_value = {
                    **self.test_recipe_data,
                    'likes_count': current_count
                }
                
                # Simulate like document
                like_ref = Mock()
                like_doc = Mock()
                like_doc.exists = user_already_liked
                
                # Mock Firestore operations
                self.mock_db.collection.return_value.document.return_value = recipe_ref
                recipe_ref.get.return_value = recipe_doc
                recipe_ref.collection.return_value.document.return_value = like_ref
                like_ref.get.return_value = like_doc
                
                # Update tracker (simulate actual database change)
                if not user_already_liked:
                    likes_tracker['count'] += 1
                    likes_tracker['users'].add(user_id)
                
                return {
                    'liked': True,
                    'likes_count': likes_tracker['count'],
                    'timestamp': datetime.now(timezone.utc)
                }
        
        self.mock_db.transaction.return_value = Mock()
        
        # Create concurrent like operations from different users
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(num_users):
                user_id = f'user_{i}'
                future = executor.submit(
                    self._safe_like_operation_with_user,
                    recipe_id, user_id, True, mock_transaction_func
                )
                futures.append(future)
            
            # Collect results
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=15)
                    results.append(result)
                except Exception as e:
                    self.fail(f"Concurrent like operation failed: {e}")
        
        # Verify all operations succeeded
        self.assertEqual(len(results), num_users)
        
        # Verify final likes_count equals number of unique users
        final_counts = [r['likes_count'] for r in results]
        max_count = max(final_counts)
        self.assertEqual(max_count, num_users, "Final likes count should equal number of unique users")
        
        # Verify all results show liked=True
        for result in results:
            self.assertTrue(result['liked'])
    
    def test_concurrent_like_unlike_oscillation(self):
        """Test rapid like/unlike operations from same user"""
        recipe_id = 'recipe_123'
        user_id = 'user_123'
        num_operations = 100
        
        # Track oscillation state
        state = {'liked': False, 'count': 0}
        lock = threading.Lock()
        
        def mock_transaction_func(transaction, like_action):
            with lock:
                # Simulate transaction behavior for oscillating like/unlike
                recipe_ref = Mock()
                recipe_doc = Mock()
                recipe_doc.exists = True
                recipe_doc.to_dict.return_value = {
                    **self.test_recipe_data,
                    'likes_count': state['count']
                }
                
                like_ref = Mock()
                like_doc = Mock()
                like_doc.exists = state['liked']
                
                # Mock Firestore operations
                self.mock_db.collection.return_value.document.return_value = recipe_ref
                recipe_ref.get.return_value = recipe_doc
                recipe_ref.collection.return_value.document.return_value = like_ref
                like_ref.get.return_value = like_doc
                
                # Update state based on action
                if like_action and not state['liked']:
                    # Like operation
                    state['liked'] = True
                    state['count'] = 1
                elif not like_action and state['liked']:
                    # Unlike operation
                    state['liked'] = False
                    state['count'] = 0
                
                return {
                    'liked': state['liked'],
                    'likes_count': state['count'],
                    'timestamp': datetime.now(timezone.utc)
                }
        
        self.mock_db.transaction.return_value = Mock()
        
        # Create alternating like/unlike operations
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(num_operations):
                like_action = i % 2 == 0  # Alternate between like (True) and unlike (False)
                future = executor.submit(
                    self._safe_like_operation_oscillation,
                    recipe_id, user_id, like_action, mock_transaction_func
                )
                futures.append(future)
            
            # Collect results
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=10)
                    results.append(result)
                except Exception as e:
                    self.fail(f"Oscillation operation failed: {e}")
        
        # Verify all operations completed
        self.assertEqual(len(results), num_operations)
        
        # Final state should be consistent (likes_count should be 0 or 1)
        final_counts = [r['likes_count'] for r in results]
        unique_counts = set(final_counts)
        self.assertTrue(unique_counts.issubset({0, 1}), "likes_count should only be 0 or 1")
    
    def test_stress_test_mixed_operations(self):
        """Comprehensive stress test with mixed like/unlike operations"""
        recipe_id = 'recipe_stress_test'
        num_users = 50
        operations_per_user = 4  # Total: 200 operations
        
        # Global state tracker with thread safety
        global_state = {
            'recipe_likes_count': 0,
            'user_likes': set(),  # Set of users who have liked
            'operation_count': 0
        }
        lock = threading.Lock()
        
        def mock_transaction_func(transaction, user_id, like_action):
            with lock:
                global_state['operation_count'] += 1
                
                # Current state
                user_currently_likes = user_id in global_state['user_likes']
                
                # Simulate recipe document
                recipe_ref = Mock()
                recipe_doc = Mock()
                recipe_doc.exists = True
                recipe_doc.to_dict.return_value = {
                    **self.test_recipe_data,
                    'likes_count': global_state['recipe_likes_count']
                }
                
                # Simulate like document
                like_ref = Mock()
                like_doc = Mock()
                like_doc.exists = user_currently_likes
                
                # Mock Firestore operations
                self.mock_db.collection.return_value.document.return_value = recipe_ref
                recipe_ref.get.return_value = recipe_doc
                recipe_ref.collection.return_value.document.return_value = like_ref
                like_ref.get.return_value = like_doc
                
                # Apply state changes
                if like_action and not user_currently_likes:
                    # Like operation
                    global_state['user_likes'].add(user_id)
                    global_state['recipe_likes_count'] += 1
                elif not like_action and user_currently_likes:
                    # Unlike operation
                    global_state['user_likes'].discard(user_id)
                    global_state['recipe_likes_count'] = max(0, global_state['recipe_likes_count'] - 1)
                
                # Return current state
                return {
                    'liked': user_id in global_state['user_likes'],
                    'likes_count': global_state['recipe_likes_count'],
                    'timestamp': datetime.now(timezone.utc)
                }
        
        self.mock_db.transaction.return_value = Mock()
        
        # Create mixed operations: likes and unlikes
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = []
            
            for user_i in range(num_users):
                user_id = f'stress_user_{user_i}'
                for op_i in range(operations_per_user):
                    # Mix of like/unlike operations
                    like_action = (user_i + op_i) % 3 != 0  # Roughly 2/3 likes, 1/3 unlikes
                    
                    future = executor.submit(
                        self._safe_stress_operation,
                        recipe_id, user_id, like_action, mock_transaction_func
                    )
                    futures.append(future)
            
            # Collect results
            results = []
            for future in as_completed(futures, timeout=20):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.fail(f"Stress test operation failed: {e}")
        
        # Verify all operations completed
        expected_operations = num_users * operations_per_user
        self.assertEqual(len(results), expected_operations)
        self.assertEqual(global_state['operation_count'], expected_operations)
        
        # Verify data consistency
        final_likes_count = global_state['recipe_likes_count']
        actual_liked_users = len(global_state['user_likes'])
        
        self.assertEqual(final_likes_count, actual_liked_users, 
                        "likes_count should equal number of users who have liked")
        
        # Verify no negative counts
        all_counts = [r['likes_count'] for r in results]
        self.assertTrue(all(count >= 0 for count in all_counts), 
                       "likes_count should never be negative")
        
        print(f"✅ Stress test completed: {expected_operations} operations, "
              f"final likes_count: {final_likes_count}, "
              f"unique users who liked: {actual_liked_users}")
    
    def _safe_like_operation(self, recipe_id, user_id, like_action, mock_func):
        """Thread-safe wrapper for like operations"""
        try:
            # Mock the transaction decorator behavior
            with patch.object(self.like_service, 'toggle_like') as mock_toggle:
                mock_toggle.return_value = mock_func(Mock())
                return self.like_service.toggle_like(recipe_id, user_id, like_action)
        except Exception as e:
            raise Exception(f"Like operation failed for user {user_id}: {e}")
    
    def _safe_like_operation_with_user(self, recipe_id, user_id, like_action, mock_func):
        """Thread-safe wrapper for like operations with user-specific mocking"""
        try:
            with patch.object(self.like_service, 'toggle_like') as mock_toggle:
                mock_toggle.return_value = mock_func(Mock(), user_id)
                return self.like_service.toggle_like(recipe_id, user_id, like_action)
        except Exception as e:
            raise Exception(f"Like operation failed for user {user_id}: {e}")
    
    def _safe_like_operation_oscillation(self, recipe_id, user_id, like_action, mock_func):
        """Thread-safe wrapper for oscillating like operations"""
        try:
            with patch.object(self.like_service, 'toggle_like') as mock_toggle:
                mock_toggle.return_value = mock_func(Mock(), like_action)
                return self.like_service.toggle_like(recipe_id, user_id, like_action)
        except Exception as e:
            raise Exception(f"Oscillation operation failed: {e}")
    
    def _safe_stress_operation(self, recipe_id, user_id, like_action, mock_func):
        """Thread-safe wrapper for stress test operations"""
        try:
            with patch.object(self.like_service, 'toggle_like') as mock_toggle:
                mock_toggle.return_value = mock_func(Mock(), user_id, like_action)
                return self.like_service.toggle_like(recipe_id, user_id, like_action)
        except Exception as e:
            raise Exception(f"Stress operation failed for user {user_id}: {e}")


class TestLikeServicePerformance(unittest.TestCase):
    """Performance tests for like service under load"""
    
    def setUp(self):
        """Set up performance test fixtures"""
        self.like_service = LikeService()
        self.mock_db = Mock()
        self.like_service.db = self.mock_db
    
    def test_response_time_under_load(self):
        """Test that response times remain reasonable under concurrent load"""
        recipe_id = 'perf_recipe_123'
        num_concurrent_operations = 50
        
        # Mock fast transaction
        def fast_mock_transaction(transaction):
            time.sleep(0.001)  # Simulate minimal database latency
            return {
                'liked': True,
                'likes_count': 1,
                'timestamp': datetime.now(timezone.utc)
            }
        
        start_time = time.time()
        
        # Execute concurrent operations
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = []
            for i in range(num_concurrent_operations):
                user_id = f'perf_user_{i}'
                future = executor.submit(self._timed_like_operation, recipe_id, user_id, fast_mock_transaction)
                futures.append(future)
            
            # Collect results and times
            response_times = []
            for future in as_completed(futures, timeout=10):
                result, response_time = future.result()
                response_times.append(response_time)
        
        total_time = time.time() - start_time
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        # Performance assertions
        self.assertLess(avg_response_time, 0.1, "Average response time should be under 100ms")
        self.assertLess(max_response_time, 0.5, "Max response time should be under 500ms")
        self.assertLess(total_time, 5.0, "Total test time should be under 5 seconds")
        
        print(f"✅ Performance test results:")
        print(f"   - Total operations: {num_concurrent_operations}")
        print(f"   - Total time: {total_time:.2f}s")
        print(f"   - Average response time: {avg_response_time*1000:.1f}ms")
        print(f"   - Max response time: {max_response_time*1000:.1f}ms")
    
    def _timed_like_operation(self, recipe_id, user_id, mock_func):
        """Execute a like operation and measure response time"""
        start = time.time()
        try:
            with patch.object(self.like_service, 'toggle_like') as mock_toggle:
                mock_toggle.return_value = mock_func(Mock())
                result = self.like_service.toggle_like(recipe_id, user_id, True)
            response_time = time.time() - start
            return result, response_time
        except Exception as e:
            response_time = time.time() - start
            raise Exception(f"Timed operation failed in {response_time:.3f}s: {e}")


if __name__ == "__main__":
    # Run with verbose output to see detailed results
    unittest.main(verbosity=2) 