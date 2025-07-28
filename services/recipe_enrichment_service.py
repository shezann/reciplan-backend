"""
Recipe Enrichment Service for adding user-specific data to recipe responses
"""

from typing import List, Dict, Any, Optional
from services.like_service import like_service


class RecipeEnrichmentService:
    """Service for enriching recipe data with user-specific information"""
    
    def __init__(self):
        self.like_service = like_service
    
    def enrich_recipe_with_user_data(self, recipe: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrich a single recipe with user-specific data
        
        Args:
            recipe: Recipe dictionary
            user_id: Current user ID (None for unauthenticated users)
            
        Returns:
            Recipe dictionary with added user-specific fields
        """
        # Add liked status
        if user_id:
            try:
                recipe['liked'] = self.like_service.has_liked(recipe['id'], user_id) or False
            except Exception as e:
                print(f"[RecipeEnrichment] Error checking like status: {e}")
                recipe['liked'] = False
        else:
            recipe['liked'] = False  # Unauthenticated users haven't liked anything
        
        # Add created_by_me status
        recipe['created_by_me'] = recipe.get('user_id') == user_id if user_id else False
        
        # Add saved status (if saved_by array exists)
        saved_by = recipe.get('saved_by', [])
        if user_id:
            recipe['saved'] = user_id in saved_by
        else:
            recipe['saved'] = False
        
        return recipe
    
    def enrich_recipes_with_user_data(self, recipes: List[Dict[str, Any]], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Enrich multiple recipes with user-specific data (optimized for batch operations)
        
        Args:
            recipes: List of recipe dictionaries
            user_id: Current user ID (None for unauthenticated users)
            
        Returns:
            List of enriched recipe dictionaries
        """
        if not recipes:
            return []
        
        # For performance, we could batch the like status checks
        # But for now, we'll enrich each recipe individually
        enriched_recipes = []
        for recipe in recipes:
            enriched_recipe = self.enrich_recipe_with_user_data(recipe, user_id)
            enriched_recipes.append(enriched_recipe)
        
        return enriched_recipes
    
    def get_user_recipes(self, user_id: str, page: int = 1, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recipes that user either created OR liked (for "My Recipes" tab)
        
        Args:
            user_id: User ID
            page: Page number (1-based)
            limit: Number of recipes per page
            
        Returns:
            List of recipes (created + liked by user)
        """
        try:
            # Import here to avoid circular imports
            from services.firestore_service import recipe_service
            
            # 1. Get recipes created by user
            created_recipes = recipe_service.get_recipes(user_id=user_id, limit=limit)
            
            # 2. Get recipe IDs that user liked
            liked_recipe_ids = self.like_service.get_user_likes(user_id, limit=limit)
            
            # 3. Fetch the actual liked recipe documents
            liked_recipes = []
            for recipe_id in liked_recipe_ids:
                recipe = recipe_service.get_recipe_by_id(recipe_id)
                if recipe and recipe not in created_recipes:  # Avoid duplicates
                    liked_recipes.append(recipe)
            
            # 4. Combine and sort by updated_at or created_at
            all_recipes = created_recipes + liked_recipes
            
            # Sort by most recent first
            all_recipes.sort(key=lambda r: r.get('updated_at', r.get('created_at', '')), reverse=True)
            
            # 5. Apply pagination
            start_index = (page - 1) * limit
            end_index = start_index + limit
            paginated_recipes = all_recipes[start_index:end_index]
            
            # 6. Enrich with user data
            enriched_recipes = self.enrich_recipes_with_user_data(paginated_recipes, user_id)
            
            return enriched_recipes
            
        except Exception as e:
            print(f"[RecipeEnrichment] Error getting user recipes: {e}")
            return []
    
    def get_liked_recipes(self, user_id: str, page: int = 1, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get only recipes that user has liked
        
        Args:
            user_id: User ID
            page: Page number (1-based) 
            limit: Number of recipes per page
            
        Returns:
            List of liked recipes
        """
        try:
            from services.firestore_service import recipe_service
            
            # Get recipe IDs that user liked
            all_liked_recipe_ids = self.like_service.get_user_likes(user_id, limit=1000)
            
            # Apply pagination to IDs first
            start_index = (page - 1) * limit
            end_index = start_index + limit
            paginated_recipe_ids = all_liked_recipe_ids[start_index:end_index]
            
            # Fetch the actual recipe documents
            liked_recipes = []
            for recipe_id in paginated_recipe_ids:
                recipe = recipe_service.get_recipe_by_id(recipe_id)
                if recipe:
                    liked_recipes.append(recipe)
            
            # Enrich with user data (will have liked=True for all)
            enriched_recipes = self.enrich_recipes_with_user_data(liked_recipes, user_id)
            
            return enriched_recipes
            
        except Exception as e:
            print(f"[RecipeEnrichment] Error getting liked recipes: {e}")
            return []


# Create service instance
recipe_enrichment_service = RecipeEnrichmentService() 