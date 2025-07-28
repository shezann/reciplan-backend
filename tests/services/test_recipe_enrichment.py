#!/usr/bin/env python3
"""
Tests for Recipe Enrichment Service
Tests the boolean approach for user-specific recipe data
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.recipe_enrichment_service import RecipeEnrichmentService


class TestRecipeEnrichmentService(unittest.TestCase):
    """Test recipe enrichment with user-specific data"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.enrichment_service = RecipeEnrichmentService()
        
        # Sample recipe data
        self.sample_recipe = {
            'id': 'recipe_123',
            'title': 'Test Recipe',
            'description': 'A test recipe',
            'user_id': 'recipe_owner_456',
            'likes_count': 5,
            'last_liked_by': 'some_user',
            'saved_by': ['user_1', 'user_2', 'test_user']
        }
    
    def test_enrich_recipe_authenticated_user_liked(self):
        """Test enriching recipe for authenticated user who liked it"""
        # Mock like service to return True (user liked this recipe)
        with patch.object(self.enrichment_service.like_service, 'has_liked', return_value=True):
            enriched = self.enrichment_service.enrich_recipe_with_user_data(
                self.sample_recipe.copy(), 
                user_id='test_user'
            )
        
        # Verify boolean fields are added correctly
        self.assertTrue(enriched['liked'])  # User liked this recipe
        self.assertFalse(enriched['created_by_me'])  # User didn't create it
        self.assertTrue(enriched['saved'])  # User saved it (in saved_by array)
        
        # Verify original data is preserved
        self.assertEqual(enriched['id'], 'recipe_123')
        self.assertEqual(enriched['likes_count'], 5)
    
    def test_enrich_recipe_authenticated_user_not_liked(self):
        """Test enriching recipe for authenticated user who hasn't liked it"""
        # Mock like service to return False
        with patch.object(self.enrichment_service.like_service, 'has_liked', return_value=False):
            enriched = self.enrichment_service.enrich_recipe_with_user_data(
                self.sample_recipe.copy(), 
                user_id='different_user'
            )
        
        # Verify boolean fields
        self.assertFalse(enriched['liked'])  # User didn't like this recipe
        self.assertFalse(enriched['created_by_me'])  # User didn't create it
        self.assertFalse(enriched['saved'])  # User didn't save it
    
    def test_enrich_recipe_authenticated_user_is_creator(self):
        """Test enriching recipe for user who created it"""
        # Mock like service to return False (creator didn't like their own recipe)
        with patch.object(self.enrichment_service.like_service, 'has_liked', return_value=False):
            enriched = self.enrichment_service.enrich_recipe_with_user_data(
                self.sample_recipe.copy(), 
                user_id='recipe_owner_456'  # Same as recipe's user_id
            )
        
        # Verify boolean fields
        self.assertFalse(enriched['liked'])  # Creator didn't like their own recipe
        self.assertTrue(enriched['created_by_me'])  # User created this recipe
        self.assertFalse(enriched['saved'])  # Creator not in saved_by array
    
    def test_enrich_recipe_unauthenticated_user(self):
        """Test enriching recipe for unauthenticated user"""
        enriched = self.enrichment_service.enrich_recipe_with_user_data(
            self.sample_recipe.copy(), 
            user_id=None  # Unauthenticated
        )
        
        # Verify all boolean fields are False for unauthenticated users
        self.assertFalse(enriched['liked'])
        self.assertFalse(enriched['created_by_me'])
        self.assertFalse(enriched['saved'])
    
    def test_enrich_recipe_like_service_error(self):
        """Test enriching recipe when like service throws error"""
        # Mock like service to throw an exception
        with patch.object(self.enrichment_service.like_service, 'has_liked', side_effect=Exception("Database error")):
            enriched = self.enrichment_service.enrich_recipe_with_user_data(
                self.sample_recipe.copy(), 
                user_id='test_user'
            )
        
        # Should gracefully handle error and set liked to False
        self.assertFalse(enriched['liked'])
    
    def test_enrich_multiple_recipes(self):
        """Test enriching multiple recipes at once"""
        recipes = [
            {
                'id': 'recipe_1',
                'title': 'Recipe 1',
                'user_id': 'owner_1',
                'likes_count': 10,
                'saved_by': ['test_user']
            },
            {
                'id': 'recipe_2', 
                'title': 'Recipe 2',
                'user_id': 'test_user',  # User created this one
                'likes_count': 20,
                'saved_by': []
            }
        ]
        
        # Mock like service responses
        def mock_has_liked(recipe_id, user_id):
            return recipe_id == 'recipe_1'  # User liked only recipe_1
        
        with patch.object(self.enrichment_service.like_service, 'has_liked', side_effect=mock_has_liked):
            enriched_recipes = self.enrichment_service.enrich_recipes_with_user_data(
                recipes, 
                user_id='test_user'
            )
        
        # Verify first recipe (liked, saved, not created)
        self.assertTrue(enriched_recipes[0]['liked'])
        self.assertTrue(enriched_recipes[0]['saved'])
        self.assertFalse(enriched_recipes[0]['created_by_me'])
        
        # Verify second recipe (not liked, not saved, but created)
        self.assertFalse(enriched_recipes[1]['liked'])
        self.assertFalse(enriched_recipes[1]['saved'])
        self.assertTrue(enriched_recipes[1]['created_by_me'])
    
    def test_enrich_empty_recipe_list(self):
        """Test enriching empty recipe list"""
        enriched = self.enrichment_service.enrich_recipes_with_user_data([], user_id='test_user')
        self.assertEqual(enriched, [])
    
    @patch('services.recipe_enrichment_service.recipe_service')
    def test_get_user_recipes(self, mock_recipe_service):
        """Test getting user's created and liked recipes"""
        # Mock created recipes
        mock_recipe_service.get_recipes.return_value = [
            {'id': 'created_1', 'title': 'My Recipe', 'user_id': 'test_user', 'updated_at': '2025-01-27T10:00:00Z'}
        ]
        
        # Mock recipe_service.get_recipe_by_id for liked recipes
        mock_recipe_service.get_recipe_by_id.return_value = {
            'id': 'liked_1', 'title': 'Liked Recipe', 'user_id': 'other_user', 'updated_at': '2025-01-27T11:00:00Z'
        }
        
        # Mock like service
        with patch.object(self.enrichment_service.like_service, 'get_user_likes', return_value=['liked_1']):
            with patch.object(self.enrichment_service.like_service, 'has_liked') as mock_has_liked:
                # Configure has_liked responses
                def mock_has_liked_response(recipe_id, user_id):
                    return recipe_id == 'liked_1'
                mock_has_liked.side_effect = mock_has_liked_response
                
                user_recipes = self.enrichment_service.get_user_recipes('test_user', page=1, limit=10)
        
        # Should return both created and liked recipes
        self.assertEqual(len(user_recipes), 2)
        
        # Verify enrichment worked
        recipe_ids = [r['id'] for r in user_recipes]
        self.assertIn('created_1', recipe_ids)
        self.assertIn('liked_1', recipe_ids)
    
    @patch('services.recipe_enrichment_service.recipe_service')
    def test_get_liked_recipes(self, mock_recipe_service):
        """Test getting only recipes that user liked"""
        # Mock recipe_service.get_recipe_by_id
        mock_recipe_service.get_recipe_by_id.return_value = {
            'id': 'liked_recipe', 'title': 'Liked Recipe', 'user_id': 'other_user'
        }
        
        # Mock like service
        with patch.object(self.enrichment_service.like_service, 'get_user_likes', return_value=['liked_recipe']):
            with patch.object(self.enrichment_service.like_service, 'has_liked', return_value=True):
                liked_recipes = self.enrichment_service.get_liked_recipes('test_user', page=1, limit=10)
        
        # Should return liked recipes with liked=True
        self.assertEqual(len(liked_recipes), 1)
        self.assertEqual(liked_recipes[0]['id'], 'liked_recipe')
        self.assertTrue(liked_recipes[0]['liked'])  # Should be True since it's a liked recipe
    
    def test_recipe_missing_fields(self):
        """Test enriching recipe with missing optional fields"""
        minimal_recipe = {
            'id': 'minimal_recipe',
            'title': 'Minimal Recipe'
            # Missing user_id, saved_by, etc.
        }
        
        with patch.object(self.enrichment_service.like_service, 'has_liked', return_value=False):
            enriched = self.enrichment_service.enrich_recipe_with_user_data(
                minimal_recipe, 
                user_id='test_user'
            )
        
        # Should handle missing fields gracefully
        self.assertFalse(enriched['liked'])
        self.assertFalse(enriched['created_by_me'])  # No user_id to compare
        self.assertFalse(enriched['saved'])  # No saved_by array


class TestRecipeEnrichmentIntegration(unittest.TestCase):
    """Integration tests for recipe enrichment"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.enrichment_service = RecipeEnrichmentService()
    
    def test_boolean_approach_vs_array_approach_performance(self):
        """Test that boolean approach is more efficient than array approach"""
        # Simulate a recipe with many likes (array approach would be huge)
        recipe_with_many_likes = {
            'id': 'popular_recipe',
            'title': 'Very Popular Recipe',
            'user_id': 'chef_user',
            'likes_count': 10000,  # 10K likes
            'saved_by': ['user_1', 'user_2']  # Only 2 saves
        }
        
        # Mock like service for current user
        with patch.object(self.enrichment_service.like_service, 'has_liked', return_value=True):
            start_time = __import__('time').time()
            
            # Enrich recipe - should be fast regardless of likes_count
            enriched = self.enrichment_service.enrich_recipe_with_user_data(
                recipe_with_many_likes, 
                user_id='test_user'
            )
            
            end_time = __import__('time').time()
            processing_time = end_time - start_time
        
        # Verify boolean approach results
        self.assertTrue(enriched['liked'])  # Single boolean, not huge array
        self.assertEqual(enriched['likes_count'], 10000)  # Preserve count
        
        # Performance should be fast (< 1 second even with 10K likes)
        self.assertLess(processing_time, 1.0)
        
        # Verify response size is small (boolean vs large array)
        import json
        response_size = len(json.dumps(enriched))
        
        # Should be much smaller than if we included 10K user IDs
        self.assertLess(response_size, 1000)  # Less than 1KB


if __name__ == "__main__":
    unittest.main(verbosity=2) 