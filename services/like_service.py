"""
Like service for handling recipe like/unlike operations with Firestore transactions
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union, List
from google.cloud.firestore_v1 import Transaction
from google.cloud import firestore

from config.firebase_config import get_firestore_db, is_firebase_available


class LikeServiceError(Exception):
    """Base exception for like service errors"""
    pass


class RecipeNotFoundError(LikeServiceError):
    """Recipe does not exist"""
    pass


class UserNotFoundError(LikeServiceError):
    """User does not exist or is invalid"""
    pass


class InvalidInputError(LikeServiceError):
    """Invalid input data provided"""
    pass


class PermissionDeniedError(LikeServiceError):
    """User does not have permission to perform this action"""
    pass


class RecipeNotAvailableError(LikeServiceError):
    """Recipe exists but is not available for liking"""
    pass


class LikeService:
    """Service for managing recipe likes with transaction safety"""
    
    # Constants for validation
    MAX_RECIPE_ID_LENGTH = 100
    MAX_USER_ID_LENGTH = 100
    RECIPE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]+$')
    
    def __init__(self):
        self.db = get_firestore_db()
    
    def _validate_recipe_id(self, recipe_id: str) -> None:
        """
        Validate recipe ID format and constraints
        
        Args:
            recipe_id: Recipe ID to validate
            
        Raises:
            InvalidInputError: If recipe ID is invalid
        """
        if not recipe_id:
            raise InvalidInputError("Recipe ID is required")
        
        if not isinstance(recipe_id, str):
            raise InvalidInputError("Recipe ID must be a string")
        
        recipe_id = recipe_id.strip()
        if not recipe_id:
            raise InvalidInputError("Recipe ID cannot be empty or whitespace")
        
        if len(recipe_id) > self.MAX_RECIPE_ID_LENGTH:
            raise InvalidInputError(f"Recipe ID too long (max {self.MAX_RECIPE_ID_LENGTH} characters)")
        
        if not self.RECIPE_ID_PATTERN.match(recipe_id):
            raise InvalidInputError("Recipe ID contains invalid characters (only alphanumeric, underscore, hyphen allowed)")
    
    def _validate_user_id(self, user_id: str) -> None:
        """
        Validate user ID format and constraints
        
        Args:
            user_id: User ID to validate
            
        Raises:
            InvalidInputError: If user ID is invalid
        """
        if not user_id:
            raise InvalidInputError("User ID is required")
        
        if not isinstance(user_id, str):
            raise InvalidInputError("User ID must be a string")
        
        user_id = user_id.strip()
        if not user_id:
            raise InvalidInputError("User ID cannot be empty or whitespace")
        
        if len(user_id) > self.MAX_USER_ID_LENGTH:
            raise InvalidInputError(f"User ID too long (max {self.MAX_USER_ID_LENGTH} characters)")
        
        if not self.USER_ID_PATTERN.match(user_id):
            raise InvalidInputError("User ID contains invalid characters")
    
    def _validate_user_exists_and_active(self, user_id: str) -> None:
        """
        Validate that user exists and is in good standing
        
        Args:
            user_id: User ID to validate
            
        Raises:
            UserNotFoundError: If user doesn't exist
            PermissionDeniedError: If user is banned/suspended
        """
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                raise UserNotFoundError(f"User {user_id} does not exist")
            
            user_data = user_doc.to_dict()
            
            # Check user status
            user_status = user_data.get('status', 'active')
            if user_status == 'deleted':
                raise UserNotFoundError(f"User {user_id} has been deleted")
            elif user_status == 'banned':
                raise PermissionDeniedError(f"User {user_id} is banned")
            elif user_status == 'suspended':
                raise PermissionDeniedError(f"User {user_id} is suspended")
            elif user_status != 'active':
                raise PermissionDeniedError(f"User {user_id} account is not active")
            
        except (UserNotFoundError, PermissionDeniedError):
            raise
        except Exception as e:
            print(f"[LikeService] Error validating user {user_id}: {e}")
            # Default to allowing operation if we can't verify user status
            # This prevents false negatives due to temporary database issues
            pass
    
    def _validate_recipe_exists_and_available(self, recipe_id: str, user_id: str) -> Dict[str, Any]:
        """
        Validate that recipe exists and is available for liking
        
        Args:
            recipe_id: Recipe ID to validate
            user_id: User ID attempting to like
            
        Returns:
            Recipe data dictionary
            
        Raises:
            RecipeNotFoundError: If recipe doesn't exist
            RecipeNotAvailableError: If recipe is not available for liking
            PermissionDeniedError: If user cannot like this recipe
        """
        try:
            recipe_ref = self.db.collection('recipes').document(recipe_id)
            recipe_doc = recipe_ref.get()
            
            if not recipe_doc.exists:
                raise RecipeNotFoundError(f"Recipe {recipe_id} does not exist")
            
            recipe_data = recipe_doc.to_dict()
            
            # Check recipe status
            recipe_status = recipe_data.get('status', 'active')
            if recipe_status == 'deleted':
                raise RecipeNotFoundError(f"Recipe {recipe_id} has been deleted")
            elif recipe_status == 'draft':
                raise RecipeNotAvailableError(f"Recipe {recipe_id} is still in draft")
            elif recipe_status == 'processing':
                raise RecipeNotAvailableError(f"Recipe {recipe_id} is still processing")
            elif recipe_status == 'private' and recipe_data.get('user_id') != user_id:
                raise PermissionDeniedError(f"Recipe {recipe_id} is private")
            elif recipe_status not in ['active', 'public']:
                # Check explicit public flag for backwards compatibility
                if not recipe_data.get('is_public', False) and recipe_data.get('user_id') != user_id:
                    raise PermissionDeniedError(f"Cannot like a private recipe you don't own")
            
            return recipe_data
            
        except (RecipeNotFoundError, RecipeNotAvailableError, PermissionDeniedError):
            raise
        except Exception as e:
            print(f"[LikeService] Error validating recipe {recipe_id}: {e}")
            raise RecipeNotFoundError(f"Could not verify recipe {recipe_id} exists")
    
    def toggle_like(self, recipe_id: str, user_id: str, like: bool) -> Optional[Dict[str, Any]]:
        """
        Toggle like status for a recipe with transaction safety
        
        Args:
            recipe_id: The recipe document ID
            user_id: The user ID performing the action
            like: True to like, False to unlike
            
        Returns:
            Dictionary with like status and count, or None if recipe not found
            {
                'liked': bool,
                'likes_count': int,
                'timestamp': datetime
            }
            
        Raises:
            InvalidInputError: If inputs are malformed
            UserNotFoundError: If user doesn't exist or is deleted
            RecipeNotFoundError: If recipe doesn't exist or is deleted
            RecipeNotAvailableError: If recipe is not available for liking
            PermissionDeniedError: If user doesn't have permission
            LikeServiceError: If database operation fails
        """
        if not self.db:
            raise LikeServiceError("Firestore database not available")
        
        # Validate inputs
        self._validate_recipe_id(recipe_id)
        self._validate_user_id(user_id)
        
        # Clean up inputs
        recipe_id = recipe_id.strip()
        user_id = user_id.strip()
        
        # Validate user exists and is active (optional check for performance)
        # self._validate_user_exists_and_active(user_id)
        
        # Use a transaction to ensure atomicity
        @firestore.transactional
        def _toggle_like_transaction(transaction: Transaction) -> Dict[str, Any]:
            # Validate recipe exists and is available within transaction
            try:
                recipe_data = self._validate_recipe_exists_and_available(recipe_id, user_id)
            except (RecipeNotFoundError, RecipeNotAvailableError, PermissionDeniedError):
                raise
            except Exception as e:
                raise LikeServiceError(f"Failed to validate recipe: {e}")
            
            # Get recipe document reference
            recipe_ref = self.db.collection('recipes').document(recipe_id)
            
            # Read recipe within transaction (double-check for race conditions)
            recipe_doc = recipe_ref.get(transaction=transaction)
            
            if not recipe_doc.exists:
                raise RecipeNotFoundError(f"Recipe {recipe_id} was deleted during operation")
            
            current_recipe_data = recipe_doc.to_dict()
            
            # Re-validate recipe status within transaction
            recipe_status = current_recipe_data.get('status', 'active')
            if recipe_status in ['deleted', 'draft', 'processing']:
                raise RecipeNotAvailableError(f"Recipe {recipe_id} is not available (status: {recipe_status})")
            
            # Get like document reference (user can only have one like per recipe)
            like_ref = recipe_ref.collection('likes').document(user_id)
            
            # Read like document within transaction
            like_doc = like_ref.get(transaction=transaction)
            
            # Current state
            currently_liked = like_doc.exists
            current_likes_count = current_recipe_data.get('likes_count', 0)
            
            # Ensure likes_count is non-negative (data integrity check)
            if current_likes_count < 0:
                print(f"[LikeService] Warning: Recipe {recipe_id} has negative likes_count: {current_likes_count}")
                current_likes_count = 0
            
            # Determine new state and actions
            timestamp = datetime.now(timezone.utc)
            
            if like and not currently_liked:
                # Like the recipe
                # Create like document
                like_data = {
                    'user_id': user_id,
                    'recipe_id': recipe_id,
                    'created_at': timestamp.isoformat() + 'Z',
                    'updated_at': timestamp.isoformat() + 'Z'
                }
                transaction.set(like_ref, like_data)
                
                # Update recipe likes_count and last_liked_by
                new_likes_count = current_likes_count + 1
                recipe_updates = {
                    'likes_count': new_likes_count,
                    'last_liked_by': user_id,
                    'updated_at': timestamp.isoformat() + 'Z'
                }
                transaction.update(recipe_ref, recipe_updates)
                
                return {
                    'liked': True,
                    'likes_count': new_likes_count,
                    'timestamp': timestamp
                }
                
            elif not like and currently_liked:
                # Unlike the recipe
                # Delete like document
                transaction.delete(like_ref)
                
                # Update recipe likes_count (ensure it doesn't go below 0)
                new_likes_count = max(0, current_likes_count - 1)
                
                # Update last_liked_by if this was the last like
                recipe_updates = {
                    'likes_count': new_likes_count,
                    'updated_at': timestamp.isoformat() + 'Z'
                }
                
                # If no more likes, clear last_liked_by
                if new_likes_count == 0:
                    recipe_updates['last_liked_by'] = None
                
                transaction.update(recipe_ref, recipe_updates)
                
                return {
                    'liked': False,
                    'likes_count': new_likes_count,
                    'timestamp': timestamp
                }
                
            else:
                # No change needed (idempotent operation)
                return {
                    'liked': currently_liked,
                    'likes_count': current_likes_count,
                    'timestamp': timestamp
                }
        
        # Execute transaction with retry logic
        try:
            transaction = self.db.transaction()
            result = _toggle_like_transaction(transaction)
            return result
            
        except (InvalidInputError, UserNotFoundError, RecipeNotFoundError, 
                RecipeNotAvailableError, PermissionDeniedError):
            # Re-raise business logic errors as-is
            raise
        except firestore.Aborted as e:
            raise LikeServiceError(f"Transaction was aborted due to conflicts: {e}")
        except firestore.DeadlineExceeded as e:
            raise LikeServiceError(f"Database operation timed out: {e}")
        except Exception as e:
            print(f"[LikeService] Unexpected error in toggle_like: {e}")
            raise LikeServiceError(f"Failed to update like status: {e}")
    
    def has_liked(self, recipe_id: str, user_id: str) -> Optional[bool]:
        """
        Check if a user has liked a specific recipe
        
        Args:
            recipe_id: The recipe document ID
            user_id: The user ID to check
            
        Returns:
            True if liked, False if not liked, None if recipe doesn't exist
            
        Raises:
            InvalidInputError: If inputs are malformed
        """
        if not self.db:
            return None
        
        try:
            # Validate inputs
            self._validate_recipe_id(recipe_id)
            self._validate_user_id(user_id)
            
            # Clean up inputs
            recipe_id = recipe_id.strip()
            user_id = user_id.strip()
            
        except InvalidInputError:
            # For has_liked, we can return None for invalid inputs
            return None
        
        try:
            # Check if recipe exists first
            recipe_ref = self.db.collection('recipes').document(recipe_id)
            recipe_doc = recipe_ref.get()
            
            if not recipe_doc.exists:
                return None  # Recipe not found
            
            recipe_data = recipe_doc.to_dict()
            
            # Check if recipe is available
            recipe_status = recipe_data.get('status', 'active')
            if recipe_status in ['deleted', 'draft', 'processing']:
                return None  # Recipe not available
            
            # Check if like document exists
            like_ref = recipe_ref.collection('likes').document(user_id)
            like_doc = like_ref.get()
            
            return like_doc.exists
            
        except Exception as e:
            print(f"[LikeService] Error checking like status: {e}")
            return None
    
    def get_recipe_likes_count(self, recipe_id: str) -> Optional[int]:
        """
        Get the total likes count for a recipe
        
        Args:
            recipe_id: The recipe document ID
            
        Returns:
            Likes count, or None if recipe doesn't exist
            
        Raises:
            InvalidInputError: If recipe ID is malformed
        """
        if not self.db:
            return None
        
        try:
            # Validate input
            self._validate_recipe_id(recipe_id)
            recipe_id = recipe_id.strip()
            
        except InvalidInputError:
            return None
        
        try:
            recipe_ref = self.db.collection('recipes').document(recipe_id)
            recipe_doc = recipe_ref.get()
            
            if not recipe_doc.exists:
                return None
            
            recipe_data = recipe_doc.to_dict()
            
            # Check if recipe is available
            recipe_status = recipe_data.get('status', 'active')
            if recipe_status in ['deleted']:
                return None  # Recipe deleted
            
            likes_count = recipe_data.get('likes_count', 0)
            return max(0, likes_count)  # Ensure non-negative
            
        except Exception as e:
            print(f"[LikeService] Error getting likes count: {e}")
            return None
    
    def get_user_likes(self, user_id: str, limit: int = 50) -> List[str]:
        """
        Get list of recipe IDs that a user has liked
        
        Args:
            user_id: The user ID
            limit: Maximum number of results to return
            
        Returns:
            List of recipe IDs
            
        Raises:
            InvalidInputError: If user ID is malformed
        """
        if not self.db:
            return []
        
        try:
            # Validate inputs
            self._validate_user_id(user_id)
            user_id = user_id.strip()
            
            if not isinstance(limit, int) or limit <= 0 or limit > 1000:
                raise InvalidInputError("Limit must be a positive integer between 1 and 1000")
                
        except InvalidInputError:
            return []
        
        try:
            # Query across all recipe collections for this user's likes
            # This is a complex query - we'll use collection group queries
            likes_query = self.db.collection_group('likes').where('user_id', '==', user_id).limit(limit)
            
            liked_recipe_ids = []
            for like_doc in likes_query.stream():
                # Extract recipe_id from the like document path
                recipe_id = like_doc.reference.parent.parent.id
                liked_recipe_ids.append(recipe_id)
            
            return liked_recipe_ids
            
        except Exception as e:
            print(f"[LikeService] Error getting user likes: {e}")
            return []


# Create service instance
like_service = LikeService() 