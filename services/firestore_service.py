"""
Firestore service layer for managing users and recipes with Firebase Authentication
"""
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from config.firebase_config import get_firestore_db, is_firebase_available
from google.cloud.firestore_v1 import FieldFilter, ArrayUnion, ArrayRemove


class FirestoreService:
    """Service class for Firestore operations"""
    
    def __init__(self):
        self.db = get_firestore_db()
    
    def _add_timestamps(self, data: Dict) -> Dict:
        """Add created_at and updated_at timestamps to document data as ISO strings"""
        now = datetime.now(timezone.utc).isoformat() + 'Z'
        data['updated_at'] = now
        if 'created_at' not in data:
            data['created_at'] = now
        return data
    
    def _clean_recipe_data(self, recipe_data: Dict) -> Dict:
        """Clean recipe data for frontend compatibility"""
        # Check if this is a TikTok-generated recipe (has recipe_json field)
        if 'recipe_json' in recipe_data and recipe_data['recipe_json']:
            # Extract the actual recipe data from recipe_json
            actual_recipe = recipe_data['recipe_json'].copy()
            
            # Add metadata from the wrapper
            actual_recipe['id'] = recipe_data.get('id', '')
            actual_recipe['owner_uid'] = recipe_data.get('owner_uid', '')
            actual_recipe['source_url'] = recipe_data.get('source_url', '')
            actual_recipe['original_job_id'] = recipe_data.get('original_job_id', '')
            actual_recipe['created_at'] = recipe_data.get('createdAt', '')
            actual_recipe['updated_at'] = recipe_data.get('updatedAt', '')
            actual_recipe['status'] = recipe_data.get('status', 'ACTIVE')
            
            # Ensure we have all required fields
            actual_recipe.setdefault('title', 'Untitled Recipe')
            actual_recipe.setdefault('description', '')
            actual_recipe.setdefault('ingredients', [])
            actual_recipe.setdefault('instructions', [])
            actual_recipe.setdefault('prep_time', 0)
            actual_recipe.setdefault('cook_time', 0)
            actual_recipe.setdefault('servings', 1)
            actual_recipe.setdefault('difficulty', 1)
            actual_recipe.setdefault('tags', [])
            actual_recipe.setdefault('nutrition', {})
            actual_recipe.setdefault('is_public', True)
            actual_recipe.setdefault('user_id', '')
            actual_recipe.setdefault('saved_by', [])
            
            return actual_recipe
        
        # For manually created recipes, return as-is
        return recipe_data
    
    def _check_firebase_available(self):
        """Check if Firebase is available and raise appropriate error if not"""
        if not is_firebase_available():
            raise Exception("Firebase not configured - database operations unavailable")


class UserService(FirestoreService):
    """Service for user-related operations"""
    
    COLLECTION_NAME = 'users'
    
    def create_user(self, user_data: Dict) -> Dict:
        """Create a new user from Firebase authentication"""
        if not is_firebase_available():
            # For testing without Firebase, return mock user
            user_data.update({
                'id': 'mock_user_' + str(hash(user_data.get('email', 'test@example.com'))),
                'username': user_data.get('username', ''),
                'google_id': user_data.get('google_id'),
                'firebase_uid': user_data.get('firebase_uid', ''),
                'preferences': user_data.get('preferences', {}),
                'dietary_restrictions': user_data.get('dietary_restrictions', []),
                'setup_completed': False,
                'profile_picture': user_data.get('profile_picture', ''),
                'phone_number': user_data.get('phone_number', ''),
                'is_active': True
            })
            user_data = self._add_timestamps(user_data)
            return user_data
        
        # Set default values for new users
        user_data.update({
            'username': user_data.get('username', ''),
            'google_id': user_data.get('google_id'),
            'firebase_uid': user_data.get('firebase_uid', ''),
            'preferences': user_data.get('preferences', {}),
            'dietary_restrictions': user_data.get('dietary_restrictions', []),
            'setup_completed': False,  # Track if user has completed setup
            'profile_picture': user_data.get('profile_picture', ''),
            'phone_number': user_data.get('phone_number', ''),
            'saved_recipes': user_data.get('saved_recipes', []),  # Track saved recipe IDs
            'is_active': True
        })
        
        # Add timestamps
        user_data = self._add_timestamps(user_data)
        
        # Create user in Firestore
        user_ref = self.db.collection(self.COLLECTION_NAME).document()
        user_ref.set(user_data)
        
        # Return user data with ID
        user_data['id'] = user_ref.id
        return user_data
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        if not is_firebase_available():
            # Return mock data for testing
            if user_id.startswith('mock_user_'):
                return {
                    'id': user_id,
                    'name': 'Test User',
                    'email': 'test@example.com',
                    'username': 'testuser',
                    'firebase_uid': 'mock_firebase_uid',
                    'setup_completed': False,
                    'preferences': {},
                    'dietary_restrictions': []
                }
            return None
        
        doc = self.db.collection(self.COLLECTION_NAME).document(user_id).get()
        if doc.exists:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return user_data
        return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        if not is_firebase_available():
            # Return mock data for testing
            return {
                'id': 'mock_user_' + str(hash(email)),
                'name': 'Test User',
                'email': email,
                'username': 'testuser',
                'firebase_uid': 'mock_firebase_uid',
                'setup_completed': False,
                'preferences': {},
                'dietary_restrictions': []
            }
        
        users = self.db.collection(self.COLLECTION_NAME).where(
            filter=FieldFilter('email', '==', email)
        ).limit(1).get()
        
        if users:
            user_doc = users[0]
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id
            return user_data
        return None
    
    def get_user_by_firebase_uid(self, firebase_uid: str) -> Optional[Dict]:
        """Get user by Firebase UID"""
        if not is_firebase_available():
            # Return mock data for testing
            return {
                'id': 'mock_user_' + str(hash(firebase_uid)),
                'name': 'Test User',
                'email': 'test@example.com',
                'username': 'testuser',
                'firebase_uid': firebase_uid,
                'setup_completed': False,
                'preferences': {},
                'dietary_restrictions': []
            }
        
        users = self.db.collection(self.COLLECTION_NAME).where(
            filter=FieldFilter('firebase_uid', '==', firebase_uid)
        ).limit(1).get()
        
        if users:
            user_doc = users[0]
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id
            return user_data
        return None
    
    def get_user_by_google_id(self, google_id: str) -> Optional[Dict]:
        """Get user by Google ID"""
        if not is_firebase_available():
            # Return mock data for testing
            return {
                'id': 'mock_user_' + str(hash(google_id)),
                'name': 'Test User',
                'email': 'test@example.com',
                'username': 'testuser',
                'firebase_uid': 'mock_firebase_uid',
                'google_id': google_id,
                'setup_completed': False,
                'preferences': {},
                'dietary_restrictions': []
            }
        
        users = self.db.collection(self.COLLECTION_NAME).where(
            filter=FieldFilter('google_id', '==', google_id)
        ).limit(1).get()
        
        if users:
            user_doc = users[0]
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id
            return user_data
        return None
    
    def create_or_update_firebase_user(self, firebase_user_data: Dict) -> Dict:
        """Create or update user from Firebase authentication"""
        firebase_uid = firebase_user_data.get('firebase_uid')
        email = firebase_user_data.get('email')
        
        if not is_firebase_available():
            # Return mock user for testing
            return {
                'id': 'mock_user_' + str(hash(firebase_uid)),
                'name': firebase_user_data.get('name', 'Test User'),
                'email': firebase_user_data.get('email', 'test@example.com'),
                'username': '',
                'firebase_uid': firebase_uid,
                'google_id': firebase_user_data.get('google_id'),
                'profile_picture': firebase_user_data.get('profile_picture', ''),
                'phone_number': firebase_user_data.get('phone_number', ''),
                'setup_completed': False,
                'preferences': {},
                'dietary_restrictions': [],
                'created_at': datetime.now(timezone.utc).isoformat() + 'Z',
                'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
            }
        
        # Check by email first to prevent duplicate users with same email
        existing_user = self.get_user_by_email(email) if email else None
        
        # If no user found by email, check by Firebase UID
        if not existing_user and firebase_uid:
            existing_user = self.get_user_by_firebase_uid(firebase_uid)
        
        if existing_user:
            # Update existing user
            updates = {
                'name': firebase_user_data.get('name', existing_user.get('name')),
                'email': firebase_user_data.get('email', existing_user.get('email')),
                'profile_picture': firebase_user_data.get('profile_picture', existing_user.get('profile_picture')),
                'phone_number': firebase_user_data.get('phone_number', existing_user.get('phone_number')),
                'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
            }
            
            # Update Firebase UID if it's different (handles Firebase UID changes)
            if firebase_uid and existing_user.get('firebase_uid') != firebase_uid:
                updates['firebase_uid'] = firebase_uid
            
            # Only update Google ID if provided
            if firebase_user_data.get('google_id'):
                updates['google_id'] = firebase_user_data['google_id']
            
            user_ref = self.db.collection(self.COLLECTION_NAME).document(existing_user['id'])
            user_ref.update(updates)
            
            return self.get_user_by_id(existing_user['id'])
        else:
            # Create new user
            user_data = {
                'name': firebase_user_data.get('name', ''),
                'email': firebase_user_data['email'],
                'firebase_uid': firebase_uid,
                'google_id': firebase_user_data.get('google_id'),
                'profile_picture': firebase_user_data.get('profile_picture', ''),
                'phone_number': firebase_user_data.get('phone_number', ''),
                'username': '',  # Will be set during setup
                'preferences': {},
                'dietary_restrictions': [],
                'setup_completed': False
            }
            
            return self.create_user(user_data)
    
    def complete_user_setup(self, user_id: str, setup_data: Dict) -> Optional[Dict]:
        """Complete user setup with username and dietary restrictions"""
        if not is_firebase_available():
            # Return mock updated user for testing
            return {
                'id': user_id,
                'name': 'Test User',
                'email': 'test@example.com',
                'username': setup_data.get('username', 'testuser'),
                'firebase_uid': 'mock_firebase_uid',
                'setup_completed': True,
                'preferences': setup_data.get('preferences', {}),
                'dietary_restrictions': setup_data.get('dietary_restrictions', []),
                'profile_picture': '',
                'phone_number': '',
                'created_at': datetime.now(timezone.utc).isoformat() + 'Z',
                'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
            }
        
        try:
            # Validate setup data
            if not setup_data.get('username') or not setup_data.get('username').strip():
                return None
            
            # Check if username is already taken
            if self.is_username_taken(setup_data['username'], user_id):
                return None
            
            updates = {
                'username': setup_data['username'].strip(),
                'dietary_restrictions': setup_data.get('dietary_restrictions', []),
                'preferences': setup_data.get('preferences', {}),
                'setup_completed': True,
                'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
            }
            
            user_ref = self.db.collection(self.COLLECTION_NAME).document(user_id)
            user_ref.update(updates)
            
            return self.get_user_by_id(user_id)
        except Exception as e:
            print(f"Error completing user setup: {e}")
            return None
    
    def is_username_taken(self, username: str, exclude_user_id: str = None) -> bool:
        """Check if username is already taken by another user"""
        if not is_firebase_available():
            # For testing, assume usernames are unique
            return False
        
        query = self.db.collection(self.COLLECTION_NAME).where(
            filter=FieldFilter('username', '==', username)
        )
        
        users = query.get()
        
        for user_doc in users:
            if exclude_user_id and user_doc.id == exclude_user_id:
                continue
            return True
        
        return False
    
    def update_user(self, user_id: str, updates: Dict) -> Optional[Dict]:
        """Update user information"""
        if not is_firebase_available():
            # Return mock updated user for testing
            return {
                'id': user_id,
                'name': updates.get('name', 'Test User'),
                'email': 'test@example.com',
                'username': updates.get('username', 'testuser'),
                'firebase_uid': 'mock_firebase_uid',
                'setup_completed': True,
                'preferences': updates.get('preferences', {}),
                'dietary_restrictions': updates.get('dietary_restrictions', []),
                'profile_picture': updates.get('profile_picture', ''),
                'phone_number': updates.get('phone_number', ''),
                'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
            }
        
        try:
            # Don't allow direct updates to sensitive fields
            forbidden_fields = ['firebase_uid', 'google_id', 'setup_completed']
            for field in forbidden_fields:
                updates.pop(field, None)
            
            # If updating username, check if it's taken
            if 'username' in updates:
                if self.is_username_taken(updates['username'], user_id):
                    return None
            
            # Add updated timestamp
            updates['updated_at'] = datetime.now(timezone.utc).isoformat() + 'Z'
            
            user_ref = self.db.collection(self.COLLECTION_NAME).document(user_id)
            user_ref.update(updates)
            
            return self.get_user_by_id(user_id)
        except Exception as e:
            print(f"Error updating user: {e}")
            return None
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user"""
        if not is_firebase_available():
            # For testing, always return success
            return True
        
        try:
            self.db.collection(self.COLLECTION_NAME).document(user_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False


class RecipeService(FirestoreService):
    """Service for recipe-related operations"""
    
    COLLECTION_NAME = 'recipes'
    
    def create_recipe(self, recipe_data: Dict) -> Dict:
        """Create a new recipe"""
        if not is_firebase_available():
            # Return mock recipe for testing
            recipe_data = self._add_timestamps(recipe_data)
            recipe_data['id'] = 'mock_recipe_' + str(hash(recipe_data.get('title', 'test')))
            return recipe_data
        
        # Set default values for new recipes
        recipe_data = {
            'title': recipe_data.get('title', ''),
            'description': recipe_data.get('description', ''),
            'ingredients': recipe_data.get('ingredients', []),
            'instructions': recipe_data.get('instructions', []),
            'prep_time': recipe_data.get('prep_time', 0),
            'cook_time': recipe_data.get('cook_time', 0),
            'difficulty': recipe_data.get('difficulty', 1),
            'servings': recipe_data.get('servings', 1),
            'tags': recipe_data.get('tags', []),
            'nutrition': recipe_data.get('nutrition', {
                'calories': 0,
                'protein': 0.0,
                'carbs': 0.0,
                'fat': 0.0
            }),
            'source_platform': recipe_data.get('source_platform', ''),
            'source_url': recipe_data.get('source_url', ''),
            'video_thumbnail': recipe_data.get('video_thumbnail', ''),
            'tiktok_author': recipe_data.get('tiktok_author', None),
            'is_public': recipe_data.get('is_public', True),
            'user_id': recipe_data.get('user_id', ''),
            'saved_by': recipe_data.get('saved_by', []),
            # Likes fields
            'likes_count': recipe_data.get('likes_count', 0),
            'last_liked_by': recipe_data.get('last_liked_by', None),
            **recipe_data  # Override with any additional fields
        }
        
        recipe_data = self._add_timestamps(recipe_data)
        
        recipe_ref = self.db.collection(self.COLLECTION_NAME).document()
        recipe_ref.set(recipe_data)
        
        recipe_data['id'] = recipe_ref.id
        return recipe_data
    
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Dict]:
        """Get recipe by ID"""
        if not is_firebase_available():
            # Return mock recipe for testing
            if recipe_id == 'mock_recipe_1':
                mock_recipe = {
                    'id': recipe_id,
                    'title': 'Test Recipe',
                    'description': 'A test recipe',
                    'ingredients': [],
                    'instructions': [],
                    'user_id': 'mock_user_123'
                }
                return self._clean_recipe_data(mock_recipe)
            elif recipe_id == 'mock_recipe_2':
                # TikTok-generated recipe (has recipe_json wrapper)
                mock_recipe = {
                    'id': recipe_id,
                    'recipe_json': {
                        'title': 'Spicy Thai Basil Beef',
                        'description': 'Authentic Thai street food made easy at home',
                        'ingredients': [
                            {'name': 'ground beef', 'quantity': '1 lb'},
                            {'name': 'thai basil', 'quantity': '1 cup'},
                            {'name': 'fish sauce', 'quantity': '2 tbsp'},
                            {'name': 'soy sauce', 'quantity': '1 tbsp'},
                            {'name': 'oyster sauce', 'quantity': '1 tbsp'},
                            {'name': 'garlic', 'quantity': '4 cloves'},
                            {'name': 'chili peppers', 'quantity': '2'},
                            {'name': 'onion', 'quantity': '1/2'}
                        ],
                        'instructions': [
                            'Heat oil in a wok over high heat',
                            'Add minced garlic and chili peppers, stir-fry until fragrant',
                            'Add ground beef and break it up',
                            'Add fish sauce, soy sauce, and oyster sauce',
                            'Add sliced onion and stir-fry',
                            'Add thai basil leaves and toss quickly',
                            'Serve hot with rice'
                        ],
                        'prep_time': 15,
                        'cook_time': 10,
                        'difficulty': 3,
                        'servings': 4,
                        'tags': ['thai', 'beef', 'spicy', 'stir-fry'],
                        'nutrition': {
                            'calories': 350,
                            'protein': 25,
                            'carbs': 5,
                            'fat': 20
                        },
                        'source_url': 'https://www.tiktok.com/@thai_chef/video/123456',
                        'tiktok_author': 'thai_chef',
                        'is_public': True,
                        'user_id': '',
                        'saved_by': []
                    },
                    'owner_uid': 'mock_user_456',
                    'source_url': 'https://www.tiktok.com/@thai_chef/video/123456',
                    'original_job_id': 'job_123',
                    'createdAt': '2025-01-01T12:00:00Z',
                    'updatedAt': '2025-01-01T12:00:00Z',
                    'status': 'ACTIVE'
                }
                return self._clean_recipe_data(mock_recipe)
            elif recipe_id.startswith('mock_recipe_'):
                mock_recipe = {
                    'id': recipe_id,
                    'title': 'Test Recipe',
                    'description': 'A test recipe',
                    'ingredients': [],
                    'instructions': [],
                    'user_id': 'mock_user_123'
                }
                return self._clean_recipe_data(mock_recipe)
            return None
        
        doc = self.db.collection(self.COLLECTION_NAME).document(recipe_id).get()
        if doc.exists:
            recipe_data = doc.to_dict()
            recipe_data['id'] = doc.id
            
            return self._clean_recipe_data(recipe_data)
        return None
    
    def get_recipes(self, limit: int = 50, **filters) -> List[Dict]:
        """Get recipes with optional filtering"""
        if not is_firebase_available():
            # Return mock recipes for testing
            return [
                {
                    'id': 'mock_recipe_1',
                    'title': 'Mock Recipe 1',
                    'description': 'A test recipe',
                    'ingredients': [],
                    'instructions': [],
                    'user_id': 'mock_user_123'
                }
            ]
        
        query = self.db.collection(self.COLLECTION_NAME)
        
        # Apply filters
        if 'user_id' in filters:
            query = query.where(filter=FieldFilter('user_id', '==', filters['user_id']))
        if 'tag' in filters:
            query = query.where(filter=FieldFilter('tags', 'array_contains', filters['tag']))
        if 'difficulty' in filters:
            query = query.where(filter=FieldFilter('difficulty', '==', filters['difficulty']))
        if 'is_public' in filters:
            query = query.where(filter=FieldFilter('is_public', '==', filters['is_public']))
        
        # Order by created_at and limit
        query = query.order_by('created_at', direction='DESCENDING').limit(limit)
        
        docs = query.get()
        recipes = []
        for doc in docs:
            recipe_data = doc.to_dict()
            recipe_data['id'] = doc.id
            
            recipes.append(self._clean_recipe_data(recipe_data))
        
        return recipes
    
    def update_recipe(self, recipe_id: str, updates: Dict) -> Optional[Dict]:
        """Update recipe information"""
        if not is_firebase_available():
            # Return mock updated recipe for testing
            return {
                'id': recipe_id,
                'title': updates.get('title', 'Updated Recipe'),
                'description': updates.get('description', 'Updated description'),
                'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
            }
        
        try:
            updates['updated_at'] = datetime.now(timezone.utc).isoformat() + 'Z'
            
            recipe_ref = self.db.collection(self.COLLECTION_NAME).document(recipe_id)
            recipe_ref.update(updates)
            
            return self.get_recipe_by_id(recipe_id)
        except Exception as e:
            print(f"Error updating recipe: {e}")
            return None
    
    def delete_recipe(self, recipe_id: str) -> bool:
        """Delete a recipe"""
        if not is_firebase_available():
            # For testing, always return success
            return True
        
        try:
            self.db.collection(self.COLLECTION_NAME).document(recipe_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting recipe: {e}")
            return False
    
    def get_recipe_feed(self, page: int = 1, limit: int = 10) -> List[Dict]:
        """Get recipe feed with pagination - includes system recipes and public user recipes"""
        if not is_firebase_available():
            # Return mock recipes for testing - mix of regular and TikTok-generated recipes
            mock_recipes_raw = [
                # Regular recipe (manual creation)
                {
                    'id': 'mock_recipe_1',
                    'title': 'Caramelized Onion and Garlic Spaghetti',
                    'description': 'Minimal effort, max comfort. Sweet, savory, a little spicy... this one hits every note.',
                    'ingredients': [
                        {'name': 'large onion, thinly sliced', 'quantity': '1'},
                        {'name': 'garlic cloves, minced', 'quantity': '4'},
                        {'name': 'chili crisp', 'quantity': '2 tbsp'},
                        {'name': 'pasta', 'quantity': '8 oz'}
                    ],
                    'instructions': [
                        'Cook pasta according to package directions',
                        'Slice onions thinly and mince garlic',
                        'In a large pan, melt butter and caramelize onions'
                    ],
                    'prep_time': 10,
                    'cook_time': 20,
                    'difficulty': 2,
                    'servings': 4,
                    'tags': ['pasta', 'vegetarian', 'spicy'],
                    'source_platform': 'manual',
                    'source_url': '',
                    'tiktok_author': None,
                    'video_thumbnail': '',
                    'is_public': True,
                    'user_id': 'mock_user_123',
                    'saved_by': [],
                    'created_at': datetime.now(timezone.utc).isoformat() + 'Z',
                    'updated_at': datetime.now(timezone.utc).isoformat() + 'Z'
                },
                # TikTok-generated recipe (has recipe_json wrapper)
                {
                    'id': 'mock_recipe_2',
                    'recipe_json': {
                        'title': 'Spicy Thai Basil Beef',
                        'description': 'Authentic Thai street food made easy at home',
                        'ingredients': [
                            {'name': 'ground beef', 'quantity': '1 lb'},
                            {'name': 'thai basil', 'quantity': '1 cup'},
                            {'name': 'fish sauce', 'quantity': '2 tbsp'},
                            {'name': 'soy sauce', 'quantity': '1 tbsp'},
                            {'name': 'oyster sauce', 'quantity': '1 tbsp'},
                            {'name': 'garlic', 'quantity': '4 cloves'},
                            {'name': 'chili peppers', 'quantity': '2'},
                            {'name': 'onion', 'quantity': '1/2'}
                        ],
                        'instructions': [
                            'Heat oil in a wok over high heat',
                            'Add minced garlic and chili peppers, stir-fry until fragrant',
                            'Add ground beef and break it up',
                            'Add fish sauce, soy sauce, and oyster sauce',
                            'Add sliced onion and stir-fry',
                            'Add thai basil leaves and toss quickly',
                            'Serve hot with rice'
                        ],
                        'prep_time': 15,
                        'cook_time': 10,
                        'difficulty': 3,
                        'servings': 4,
                        'tags': ['thai', 'beef', 'spicy', 'stir-fry'],
                        'nutrition': {
                            'calories': 350,
                            'protein': 25,
                            'carbs': 5,
                            'fat': 20
                        },
                        'source_url': 'https://www.tiktok.com/@thai_chef/video/123456',
                        'tiktok_author': 'thai_chef',
                        'is_public': True,
                        'user_id': '',
                        'saved_by': []
                    },
                    'owner_uid': 'mock_user_456',
                    'source_url': 'https://www.tiktok.com/@thai_chef/video/123456',
                    'original_job_id': 'job_123',
                    'createdAt': datetime.now(timezone.utc).isoformat() + 'Z',
                    'updatedAt': datetime.now(timezone.utc).isoformat() + 'Z',
                    'status': 'ACTIVE'
                }
            ]
            
            # Process mock data through _clean_recipe_data to handle TikTok recipes
            mock_recipes = []
            for recipe_data in mock_recipes_raw:
                cleaned_recipe = self._clean_recipe_data(recipe_data)
                mock_recipes.append(cleaned_recipe)
            
            return mock_recipes
        
        try:
            # Get all recipes ordered by created_at desc
            query = self.db.collection(self.COLLECTION_NAME).order_by('created_at', direction='DESCENDING').limit(100)
            
            docs = query.get()
            recipes = []
            for doc in docs:
                recipe_data = doc.to_dict()
                recipe_data['id'] = doc.id
                
                # Clean recipe data for frontend compatibility
                recipe_data = self._clean_recipe_data(recipe_data)
                
                # Include recipes in feed if they meet either criteria:
                # 1. System recipes (user_id == "system")
                # 2. Public user recipes (is_public == True AND user_id != "system")
                user_id = recipe_data.get('user_id', '')
                is_public = recipe_data.get('is_public', False)
                
                if user_id == 'system' or (is_public and user_id != 'system'):
                    recipes.append(recipe_data)
            
            # Simple pagination by slicing results
            start_index = (page - 1) * limit
            end_index = start_index + limit
            paginated_recipes = recipes[start_index:end_index]
            
            return paginated_recipes
        except Exception as e:
            print(f"Error getting recipe feed: {e}")
            return []
    
    def save_recipe(self, recipe_id: str, user_id: str) -> bool:
        """Save/bookmark a recipe for a user"""
        if not is_firebase_available():
            # For testing, always return success
            return True
        
        try:
            # Add user_id to saved_by array
            recipe_ref = self.db.collection(self.COLLECTION_NAME).document(recipe_id)
            recipe_ref.update({
                'saved_by': ArrayUnion([user_id])
            })
            return True
        except Exception as e:
            print(f"Error saving recipe: {e}")
            return False
    
    def unsave_recipe(self, recipe_id: str, user_id: str) -> bool:
        """Unsave/unbookmark a recipe for a user"""
        if not is_firebase_available():
            # For testing, always return success
            return True
        
        try:
            # Remove user_id from saved_by array
            recipe_ref = self.db.collection(self.COLLECTION_NAME).document(recipe_id)
            recipe_ref.update({
                'saved_by': ArrayRemove([user_id])
            })
            return True
        except Exception as e:
            print(f"Error unsaving recipe: {e}")
            return False
    
    def get_saved_recipes(self, user_id: str, page: int = 1, limit: int = 10) -> List[Dict]:
        """Get recipes saved by a user"""
        if not is_firebase_available():
            # Return mock saved recipes for testing
            return [
                {
                    'id': 'mock_recipe_1',
                    'title': 'Saved Recipe',
                    'description': 'A saved recipe',
                    'prep_time': 15,
                    'cook_time': 30,
                    'difficulty': 3,
                    'video_thumbnail': 'https://picsum.photos/400/300?random=1',
                    'tiktok_author': None,
                    'saved_by': [user_id]
                }
            ]
        
        try:
            # Calculate offset for pagination
            offset = (page - 1) * limit
            
            # Get recipes where user_id is in saved_by array
            query = self.db.collection(self.COLLECTION_NAME).where(
                filter=FieldFilter('saved_by', 'array_contains', user_id)
            ).order_by('created_at', direction='DESCENDING').offset(offset).limit(limit)
            
            docs = query.get()
            recipes = []
            for doc in docs:
                recipe_data = doc.to_dict()
                recipe_data['id'] = doc.id
                recipes.append(self._clean_recipe_data(recipe_data))
            
            return recipes
        except Exception as e:
            print(f"Error getting saved recipes: {e}")
            return []


# Service instances
user_service = UserService()
recipe_service = RecipeService() 