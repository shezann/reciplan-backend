#!/usr/bin/env python3
"""
Tests for like/unlike endpoints in the like controller
"""

import unittest
from unittest.mock import Mock, patch
import json
from datetime import datetime, timezone
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import app


class TestLikeToggleEndpoints(unittest.TestCase):
    """Test cases for like/unlike endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Sample response data
        self.sample_like_response = {
            'liked': True,
            'likes_count': 1,
            'recipe_id': 'recipe123',
            'user_id': 'user123',
            'timestamp': datetime.now(timezone.utc)
        }
        
        self.sample_unlike_response = {
            'liked': False,
            'likes_count': 0,
            'recipe_id': 'recipe123',
            'user_id': 'user123',
            'timestamp': datetime.now(timezone.utc)
        }
        
        self.sample_user = {
            'id': 'user123',
            'name': 'Test User',
            'email': 'test@example.com'
        }
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_success(self, mock_get_user, mock_like_service):
        """Test successful recipe like"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service response
        mock_like_service.toggle_like.return_value = self.sample_like_response
        
        # Make request with JWT token (mocked by test client)
        with self.app.test_request_context():
            # Simulate JWT token presence
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.post('/api/recipes/recipe123/like')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['liked'])
        self.assertEqual(data['likes_count'], 1)
        self.assertEqual(data['recipe_id'], 'recipe123')
        self.assertEqual(data['user_id'], 'user123')
        
        # Verify service was called correctly
        mock_like_service.toggle_like.assert_called_once_with('recipe123', 'user123', like=True)
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_unlike_recipe_success(self, mock_get_user, mock_like_service):
        """Test successful recipe unlike"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service response
        mock_like_service.toggle_like.return_value = self.sample_unlike_response
        
        # Make request with JWT token (mocked by test client)
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.delete('/api/recipes/recipe123/like')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertFalse(data['liked'])
        self.assertEqual(data['likes_count'], 0)
        self.assertEqual(data['recipe_id'], 'recipe123')
        self.assertEqual(data['user_id'], 'user123')
        
        # Verify service was called correctly
        mock_like_service.toggle_like.assert_called_once_with('recipe123', 'user123', like=False)
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_not_found(self, mock_get_user, mock_like_service):
        """Test like recipe when recipe doesn't exist"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service response for non-existent recipe
        mock_like_service.toggle_like.return_value = None
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.post('/api/recipes/nonexistent/like')
        
        # Verify response
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_invalid_operation(self, mock_get_user, mock_like_service):
        """Test like recipe with invalid operation (business logic error)"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service to raise ValueError
        mock_like_service.toggle_like.side_effect = ValueError("Cannot like a private recipe you don't own")
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.post('/api/recipes/private_recipe/like')
        
        # Verify response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid operation')
        self.assertIn("Cannot like a private recipe", data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_user_not_found(self, mock_get_user):
        """Test like recipe when user is not found"""
        # Mock user authentication failure
        mock_get_user.return_value = None
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.post('/api/recipes/recipe123/like')
        
        # Verify response
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'User not found')
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_get_like_status_liked(self, mock_get_user, mock_like_service):
        """Test getting like status when user has liked the recipe"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service response
        mock_like_service.has_liked.return_value = True
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.get('/api/recipes/recipe123/liked')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['liked'])
        self.assertEqual(data['recipe_id'], 'recipe123')
        self.assertEqual(data['user_id'], 'user123')
        
        # Verify service was called correctly
        mock_like_service.has_liked.assert_called_once_with('recipe123', 'user123')
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_get_like_status_not_liked(self, mock_get_user, mock_like_service):
        """Test getting like status when user hasn't liked the recipe"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service response
        mock_like_service.has_liked.return_value = False
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.get('/api/recipes/recipe123/liked')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertFalse(data['liked'])
        self.assertEqual(data['recipe_id'], 'recipe123')
        self.assertEqual(data['user_id'], 'user123')
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_get_like_status_recipe_not_found(self, mock_get_user, mock_like_service):
        """Test getting like status when recipe doesn't exist"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service response for non-existent recipe
        mock_like_service.has_liked.return_value = None
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.get('/api/recipes/nonexistent/liked')
        
        # Verify response
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
    
    def test_like_recipe_unauthenticated(self):
        """Test like recipe without authentication"""
        # Make request without JWT token
        response = self.client.post('/api/recipes/recipe123/like')
        
        # Should get 401 Unauthorized due to @jwt_required decorator
        self.assertEqual(response.status_code, 422)  # JWT extension returns 422 for missing token
    
    @patch('controllers.like_controller.like_service')
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_service_error_handling(self, mock_get_user, mock_like_service):
        """Test handling of service layer errors"""
        # Mock user authentication
        mock_get_user.return_value = self.sample_user
        
        # Mock like service to raise unexpected error
        mock_like_service.toggle_like.side_effect = Exception("Database connection failed")
        
        # Make request
        with self.app.test_request_context():
            with patch('flask_jwt_extended.verify_jwt_in_request'):
                with patch('flask_jwt_extended.get_jwt_identity', return_value='user123'):
                    response = self.client.post('/api/recipes/recipe123/like')
        
        # Verify response
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Failed to like recipe')


if __name__ == "__main__":
    unittest.main() 