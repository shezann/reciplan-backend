#!/usr/bin/env python3
"""
Edge case tests for like controller operations
Tests malformed inputs, deleted users, invalid recipes, and error conditions
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from services.like_service import (
    LikeServiceError, RecipeNotFoundError, UserNotFoundError, 
    InvalidInputError, PermissionDeniedError, RecipeNotAvailableError
)


class TestLikeControllerEdgeCases(unittest.TestCase):
    """Test edge cases for like controller endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Sample user data
        self.valid_user = {
            'id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        # Valid test data
        self.valid_recipe_id = 'recipe_123'
        self.valid_jwt_token = 'valid.jwt.token'
    
    # ========== MALFORMED RECIPE ID TESTS ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_empty_recipe_id(self, mock_like_service, mock_get_user):
        """Test liking with empty recipe ID"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = InvalidInputError("Recipe ID cannot be empty or whitespace")
        
        # Test various empty recipe IDs
        empty_ids = ['', '   ', '\t\n', '/like']
        
        for empty_id in empty_ids:
            with self.subTest(recipe_id=empty_id):
                response = self.client.post(
                    f'/api/recipes/{empty_id}/like',
                    headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
                )
                
                self.assertEqual(response.status_code, 400)
                data = json.loads(response.data)
                self.assertEqual(data['error'], 'Invalid input')
                self.assertIn('Recipe ID', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_invalid_recipe_id_format(self, mock_like_service, mock_get_user):
        """Test liking with malformed recipe ID"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = InvalidInputError("Recipe ID contains invalid characters")
        
        # Test various malformed recipe IDs
        malformed_ids = [
            'recipe@123',  # Invalid character @
            'recipe 123',  # Space
            'recipe#123',  # Hash
            'recipe/123',  # Slash
            'recipe%123',  # Percent
            'recipe!123',  # Exclamation
            '../../etc/passwd',  # Path traversal attempt
            '<script>alert("xss")</script>',  # XSS attempt
            'a' * 101,  # Too long (> 100 chars)
        ]
        
        for malformed_id in malformed_ids:
            with self.subTest(recipe_id=malformed_id):
                response = self.client.post(
                    f'/api/recipes/{malformed_id}/like',
                    headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
                )
                
                self.assertEqual(response.status_code, 400)
                data = json.loads(response.data)
                self.assertEqual(data['error'], 'Invalid input')
    
    # ========== MALFORMED JSON TESTS ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_malformed_json(self, mock_get_user):
        """Test POST with malformed JSON"""
        mock_get_user.return_value = self.valid_user
        
        # Test malformed JSON payloads
        malformed_payloads = [
            '{"invalid": json}',  # Missing quotes
            '{"incomplete": ',    # Incomplete JSON
            '{invalid_key: "value"}',  # Unquoted key
            '{"valid": "json", "duplicate": "key", "duplicate": "key2"}',  # Duplicate keys
            'not_json_at_all',   # Not JSON
            '["array", "not", "object"]',  # Array instead of object
        ]
        
        for payload in malformed_payloads:
            with self.subTest(payload=payload[:30]):
                response = self.client.post(
                    f'/api/recipes/{self.valid_recipe_id}/like',
                    headers={
                        'Authorization': f'Bearer {self.valid_jwt_token}',
                        'Content-Type': 'application/json'
                    },
                    data=payload
                )
                
                self.assertEqual(response.status_code, 400)
                data = json.loads(response.data)
                self.assertIn('JSON', data['error'])
    
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_invalid_content_type(self, mock_get_user):
        """Test POST with invalid Content-Type"""
        mock_get_user.return_value = self.valid_user
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={
                'Authorization': f'Bearer {self.valid_jwt_token}',
                'Content-Type': 'text/plain'
            },
            data='some text data'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid Content-Type')
    
    # ========== USER ERROR TESTS ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_user_not_found_from_token(self, mock_get_user):
        """Test liking when user cannot be found from JWT token"""
        mock_get_user.return_value = None
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'User not found')
        self.assertIn('token', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_deleted_user(self, mock_like_service, mock_get_user):
        """Test liking with deleted user"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = UserNotFoundError("User user123 has been deleted")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'User not found')
        self.assertIn('deleted', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_banned_user(self, mock_like_service, mock_get_user):
        """Test liking with banned user"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = PermissionDeniedError("User user123 is banned")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Permission denied')
        self.assertIn('banned', data['message'])
    
    # ========== RECIPE ERROR TESTS ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_nonexistent_recipe(self, mock_like_service, mock_get_user):
        """Test liking non-existent recipe"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = RecipeNotFoundError("Recipe recipe_123 does not exist")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
        self.assertIn('does not exist', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_deleted_recipe(self, mock_like_service, mock_get_user):
        """Test liking deleted recipe"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = RecipeNotFoundError("Recipe recipe_123 has been deleted")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
        self.assertIn('deleted', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_draft_recipe(self, mock_like_service, mock_get_user):
        """Test liking recipe in draft status"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = RecipeNotAvailableError("Recipe recipe_123 is still in draft")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 422)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not available')
        self.assertIn('draft', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_processing_recipe(self, mock_like_service, mock_get_user):
        """Test liking recipe that's still processing"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = RecipeNotAvailableError("Recipe recipe_123 is still processing")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 422)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not available')
        self.assertIn('processing', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_private_recipe_not_owner(self, mock_like_service, mock_get_user):
        """Test liking private recipe by non-owner"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = PermissionDeniedError("Cannot like a private recipe you don't own")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Permission denied')
        self.assertIn('private', data['message'])
    
    # ========== SERVICE ERROR TESTS ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_database_unavailable(self, mock_like_service, mock_get_user):
        """Test liking when database is unavailable"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = LikeServiceError("Firestore database not available")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Service error')
        self.assertIn('database', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_transaction_aborted(self, mock_like_service, mock_get_user):
        """Test liking when transaction is aborted"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = LikeServiceError("Transaction was aborted due to conflicts")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Service error')
        self.assertIn('aborted', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_unexpected_error(self, mock_like_service, mock_get_user):
        """Test liking with unexpected error"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = Exception("Unexpected database error")
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Failed to like recipe')
        self.assertIn('unexpected', data['message'])
    
    # ========== UNLIKE EDGE CASES ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_unlike_nonexistent_recipe(self, mock_like_service, mock_get_user):
        """Test unliking non-existent recipe"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = RecipeNotFoundError("Recipe recipe_123 does not exist")
        
        response = self.client.delete(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_unlike_recipe_invalid_input(self, mock_like_service, mock_get_user):
        """Test unliking with invalid recipe ID"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = InvalidInputError("Recipe ID contains invalid characters")
        
        response = self.client.delete(
            f'/api/recipes/invalid@recipe/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid input')
    
    # ========== GET LIKE STATUS EDGE CASES ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_get_like_status_nonexistent_recipe(self, mock_like_service, mock_get_user):
        """Test getting like status for non-existent recipe"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.has_liked.return_value = None  # Recipe not found
        
        response = self.client.get(
            f'/api/recipes/{self.valid_recipe_id}/liked',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
        self.assertIn('not exist', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_get_like_status_invalid_recipe_id(self, mock_like_service, mock_get_user):
        """Test getting like status with invalid recipe ID"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.has_liked.return_value = None  # Invalid input returns None
        
        response = self.client.get(
            f'/api/recipes/invalid@recipe/liked',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Recipe not found')
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_get_like_status_service_error(self, mock_like_service, mock_get_user):
        """Test getting like status with service error"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.has_liked.side_effect = Exception("Database connection failed")
        
        response = self.client.get(
            f'/api/recipes/{self.valid_recipe_id}/liked',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Failed to get like status')
    
    # ========== AUTHORIZATION EDGE CASES ==========
    
    def test_like_recipe_no_auth_header(self):
        """Test liking without Authorization header"""
        response = self.client.post(f'/api/recipes/{self.valid_recipe_id}/like')
        
        # Should be handled by @jwt_required decorator
        self.assertEqual(response.status_code, 401)
    
    def test_like_recipe_invalid_jwt_token(self):
        """Test liking with invalid JWT token"""
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={'Authorization': 'Bearer invalid.jwt.token'}
        )
        
        # Should be handled by @jwt_required decorator
        self.assertEqual(response.status_code, 422)  # JWT decode error
    
    def test_like_recipe_malformed_auth_header(self):
        """Test liking with malformed Authorization header"""
        malformed_headers = [
            'invalid_format',
            'Bearer',  # Missing token
            'Basic dXNlcjpwYXNz',  # Wrong auth type
            'Bearer token1 token2',  # Multiple tokens
        ]
        
        for auth_header in malformed_headers:
            with self.subTest(auth_header=auth_header):
                response = self.client.post(
                    f'/api/recipes/{self.valid_recipe_id}/like',
                    headers={'Authorization': auth_header}
                )
                
                # Should be handled by @jwt_required decorator
                self.assertIn(response.status_code, [401, 422])
    
    # ========== STRESS EDGE CASES ==========
    
    @patch('controllers.like_controller.get_user_from_token')
    @patch('controllers.like_controller.like_service')
    def test_like_recipe_extremely_long_recipe_id(self, mock_like_service, mock_get_user):
        """Test liking with extremely long recipe ID"""
        mock_get_user.return_value = self.valid_user
        mock_like_service.toggle_like.side_effect = InvalidInputError("Recipe ID too long")
        
        # Create very long recipe ID
        long_recipe_id = 'a' * 200
        
        response = self.client.post(
            f'/api/recipes/{long_recipe_id}/like',
            headers={'Authorization': f'Bearer {self.valid_jwt_token}'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid input')
        self.assertIn('too long', data['message'])
    
    @patch('controllers.like_controller.get_user_from_token')
    def test_like_recipe_large_json_payload(self, mock_get_user):
        """Test POST with large JSON payload"""
        mock_get_user.return_value = self.valid_user
        
        # Create large JSON payload
        large_payload = {'key' + str(i): 'value' * 100 for i in range(1000)}
        
        response = self.client.post(
            f'/api/recipes/{self.valid_recipe_id}/like',
            headers={
                'Authorization': f'Bearer {self.valid_jwt_token}',
                'Content-Type': 'application/json'
            },
            json=large_payload
        )
        
        # Should either succeed (ignoring payload) or fail gracefully
        self.assertIn(response.status_code, [200, 400, 413, 500])


class TestLikeServiceEdgeCases(unittest.TestCase):
    """Test edge cases at the service level"""
    
    def setUp(self):
        """Set up service test fixtures"""
        self.mock_db = Mock()
        
        # We'll test the validation methods directly without needing full service setup
        from services.like_service import LikeService
        self.like_service = LikeService()
        self.like_service.db = self.mock_db
    
    def test_validate_recipe_id_edge_cases(self):
        """Test recipe ID validation edge cases"""
        # Valid cases should not raise
        valid_ids = ['recipe123', 'recipe_123', 'recipe-123', 'r', 'a' * 100]
        for recipe_id in valid_ids:
            try:
                self.like_service._validate_recipe_id(recipe_id)
            except InvalidInputError:
                self.fail(f"Valid recipe ID {recipe_id} should not raise InvalidInputError")
        
        # Invalid cases should raise
        invalid_cases = [
            (None, "Recipe ID is required"),
            ('', "Recipe ID cannot be empty"),
            ('   ', "Recipe ID cannot be empty or whitespace"),
            ('a' * 101, "Recipe ID too long"),
            ('recipe@123', "Recipe ID contains invalid characters"),
            ('recipe 123', "Recipe ID contains invalid characters"),
            (123, "Recipe ID must be a string"),
        ]
        
        for recipe_id, expected_error in invalid_cases:
            with self.subTest(recipe_id=recipe_id):
                with self.assertRaises(InvalidInputError) as cm:
                    self.like_service._validate_recipe_id(recipe_id)
                self.assertIn(expected_error.split()[0].lower(), str(cm.exception).lower())
    
    def test_validate_user_id_edge_cases(self):
        """Test user ID validation edge cases"""
        # Valid cases should not raise
        valid_ids = ['user123', 'user_123', 'user-123', 'user.123', 'u', 'a' * 100]
        for user_id in valid_ids:
            try:
                self.like_service._validate_user_id(user_id)
            except InvalidInputError:
                self.fail(f"Valid user ID {user_id} should not raise InvalidInputError")
        
        # Invalid cases should raise
        invalid_cases = [
            (None, "User ID is required"),
            ('', "User ID cannot be empty"),
            ('   ', "User ID cannot be empty or whitespace"),
            ('a' * 101, "User ID too long"),
            ('user@domain.com', "User ID contains invalid characters"),
            ('user space', "User ID contains invalid characters"),
            (123, "User ID must be a string"),
        ]
        
        for user_id, expected_error in invalid_cases:
            with self.subTest(user_id=user_id):
                with self.assertRaises(InvalidInputError) as cm:
                    self.like_service._validate_user_id(user_id)
                self.assertIn(expected_error.split()[0].lower(), str(cm.exception).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2) 