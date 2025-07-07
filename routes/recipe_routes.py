"""
Recipe routes for the recipe feed feature
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
from services.firestore_service import recipe_service
from services.jwt_service import get_user_from_token


# Create blueprint
recipe_bp = Blueprint('recipe', __name__, url_prefix='/api/recipes')


# Validation schemas
class RecipeFeedSchema(Schema):
    """Schema for recipe feed request"""
    page = fields.Int(required=False, load_default=1, validate=lambda x: x > 0)
    limit = fields.Int(required=False, load_default=10, validate=lambda x: 1 <= x <= 50)


class CreateRecipeSchema(Schema):
    """Schema for creating a new recipe"""
    title = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    description = fields.Str(required=False, load_default='')
    ingredients = fields.List(fields.Dict(), required=False, load_default=[])
    instructions = fields.List(fields.Str(), required=False, load_default=[])
    prep_time = fields.Int(required=False, load_default=0, validate=lambda x: x >= 0)
    cook_time = fields.Int(required=False, load_default=0, validate=lambda x: x >= 0)
    difficulty = fields.Int(required=False, load_default=1, validate=lambda x: 1 <= x <= 5)
    servings = fields.Int(required=False, load_default=1, validate=lambda x: x > 0)
    tags = fields.List(fields.Str(), required=False, load_default=[])
    nutrition = fields.Dict(required=False, load_default={})
    source_platform = fields.Str(required=False, load_default='')
    source_url = fields.Str(required=False, load_default='')
    video_thumbnail = fields.Str(required=False, load_default='')
    tiktok_author = fields.Str(required=False, load_default='')
    is_public = fields.Bool(required=False, load_default=True)


# Routes
@recipe_bp.route('/feed', methods=['GET'])
def get_recipe_feed():
    """Get recipe feed with pagination"""
    try:
        # Validate query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        
        # Validate parameters
        if page < 1:
            page = 1
        if limit < 1 or limit > 50:
            limit = 10
        
        # Get recipes from service
        recipes = recipe_service.get_recipe_feed(page=page, limit=limit)
        
        # Calculate total count and has_next
        # For simplicity, we'll get a larger sample to estimate total
        all_recipes = recipe_service.get_recipe_feed(page=1, limit=100)
        total_count = len(all_recipes)
        has_next = (page * limit) < total_count
        
        return jsonify({
            'recipes': recipes,
            'page': page,
            'limit': limit,
            'total_count': total_count,
            'has_next': has_next
        }), 200
        
    except Exception as e:
        print(f"Error getting recipe feed: {e}")
        return jsonify({
            'error': 'Failed to get recipe feed',
            'message': 'An error occurred while retrieving recipes.'
        }), 500


@recipe_bp.route('/<recipe_id>', methods=['GET'])
def get_recipe_details(recipe_id):
    """Get single recipe details"""
    try:
        recipe = recipe_service.get_recipe_by_id(recipe_id)
        
        if not recipe:
            return jsonify({
                'error': 'Recipe not found',
                'message': 'The requested recipe was not found.'
            }), 404
        
        return jsonify({
            'recipe': recipe
        }), 200
        
    except Exception as e:
        print(f"Error getting recipe details: {e}")
        return jsonify({
            'error': 'Failed to get recipe details',
            'message': 'An error occurred while retrieving the recipe.'
        }), 500


@recipe_bp.route('/<recipe_id>/save', methods=['POST'])
@jwt_required()
def save_recipe(recipe_id):
    """Save/bookmark a recipe"""
    try:
        # Get current user
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information.'
            }), 404
        
        # Check if recipe exists
        recipe = recipe_service.get_recipe_by_id(recipe_id)
        if not recipe:
            return jsonify({
                'error': 'Recipe not found',
                'message': 'The requested recipe was not found.'
            }), 404
        
        # Save recipe
        success = recipe_service.save_recipe(recipe_id, current_user['id'])
        
        if success:
            return jsonify({
                'message': 'Recipe saved successfully',
                'saved': True
            }), 200
        else:
            return jsonify({
                'error': 'Failed to save recipe',
                'message': 'An error occurred while saving the recipe.'
            }), 500
            
    except Exception as e:
        print(f"Error saving recipe: {e}")
        return jsonify({
            'error': 'Failed to save recipe',
            'message': 'An error occurred while saving the recipe.'
        }), 500


@recipe_bp.route('/<recipe_id>/save', methods=['DELETE'])
@jwt_required()
def unsave_recipe(recipe_id):
    """Unsave/unbookmark a recipe"""
    try:
        # Get current user
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information.'
            }), 404
        
        # Check if recipe exists
        recipe = recipe_service.get_recipe_by_id(recipe_id)
        if not recipe:
            return jsonify({
                'error': 'Recipe not found',
                'message': 'The requested recipe was not found.'
            }), 404
        
        # Unsave recipe
        success = recipe_service.unsave_recipe(recipe_id, current_user['id'])
        
        if success:
            return jsonify({
                'message': 'Recipe unsaved successfully',
                'saved': False
            }), 200
        else:
            return jsonify({
                'error': 'Failed to unsave recipe',
                'message': 'An error occurred while unsaving the recipe.'
            }), 500
            
    except Exception as e:
        print(f"Error unsaving recipe: {e}")
        return jsonify({
            'error': 'Failed to unsave recipe',
            'message': 'An error occurred while unsaving the recipe.'
        }), 500


@recipe_bp.route('/saved', methods=['GET'])
@jwt_required()
def get_saved_recipes():
    """Get user's saved recipes"""
    try:
        # Get current user
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information.'
            }), 404
        
        # Validate query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        
        # Validate parameters
        if page < 1:
            page = 1
        if limit < 1 or limit > 50:
            limit = 10
        
        # Get saved recipes from service
        recipes = recipe_service.get_saved_recipes(current_user['id'], page=page, limit=limit)
        
        # Calculate total count and has_next for saved recipes
        all_saved_recipes = recipe_service.get_saved_recipes(current_user['id'], page=1, limit=100)
        total_count = len(all_saved_recipes)
        has_next = (page * limit) < total_count
        
        return jsonify({
            'recipes': recipes,
            'page': page,
            'limit': limit,
            'total_count': total_count,
            'has_next': has_next
        }), 200
        
    except Exception as e:
        print(f"Error getting saved recipes: {e}")
        return jsonify({
            'error': 'Failed to get saved recipes',
            'message': 'An error occurred while retrieving saved recipes.'
        }), 500


@recipe_bp.route('/seed', methods=['POST'])
def seed_recipes():
    """Seed database with mock recipes (for development)"""
    try:
        mock_recipes = [
            {
                'title': 'Caramelized Onion and Garlic Spaghetti',
                'description': 'Minimal effort, max comfort. Sweet, savory, a little spicy... this one hits every note.',
                'ingredients': [
                    {'name': 'large onion, thinly sliced', 'quantity': '1'},
                    {'name': 'garlic cloves, minced', 'quantity': '4'},
                    {'name': 'chili crisp', 'quantity': '2 tbsp'},
                    {'name': 'cream or coconut milk', 'quantity': '1 cup'},
                    {'name': 'soy sauce', 'quantity': '1 tbsp'},
                    {'name': 'fresh Parmesan cheese, grated', 'quantity': '1/2 cup'},
                    {'name': 'pasta', 'quantity': '8 oz'},
                    {'name': 'butter', 'quantity': '2 tbsp'}
                ],
                'instructions': [
                    'Cook pasta according to package directions',
                    'Slice onions thinly and mince garlic',
                    'In a large pan, melt butter and caramelize onions',
                    'Add garlic and cook until fragrant',
                    'Add chili crisp and stir',
                    'Pour in cream and soy sauce, simmer',
                    'Toss with cooked pasta and top with Parmesan'
                ],
                'prep_time': 10,
                'cook_time': 20,
                'difficulty': 2,
                'servings': 4,
                'tags': ['pasta', 'vegetarian', 'spicy', 'comfort food'],
                'nutrition': {
                    'calories': 485,
                    'protein': 18.5,
                    'carbs': 62.0,
                    'fat': 16.2
                },
                'source_platform': 'tiktok',
                'source_url': 'https://www.tiktok.com/@recipeincaption/video/7519221347101199672',
                'video_thumbnail': 'https://picsum.photos/400/300?random=1',
                'tiktok_author': 'recipeincaption',
                'is_public': True,
                'user_id': 'system'
            },
            {
                'title': "Raising Cane's Style Chicken Tenders",
                'description': 'Crispy, juicy chicken tenders just like the famous chain restaurant',
                'ingredients': [
                    {'name': 'chicken tenderloins', 'quantity': '10 (~1.5lbs)'},
                    {'name': 'buttermilk', 'quantity': '2 cups'},
                    {'name': 'hot sauce', 'quantity': '1/4 cup'},
                    {'name': 'paprika', 'quantity': '1 tbsp'},
                    {'name': 'garlic powder', 'quantity': '1 tbsp'},
                    {'name': 'chili powder', 'quantity': '1 tbsp'},
                    {'name': 'pickle juice (optional)', 'quantity': '2 tbsp'},
                    {'name': 'self-rising flour', 'quantity': '2 cups'},
                    {'name': 'corn starch', 'quantity': '2/3 cup'}
                ],
                'instructions': [
                    'Mix buttermilk, hot sauce, and spices for marinade',
                    'Marinate chicken for at least 2 hours',
                    'Mix flour, corn starch, and spices for dry batter',
                    'Heat oil to 350°F',
                    'Dredge chicken in flour mixture',
                    'Fry for 6-8 minutes until golden brown',
                    'Drain on paper towels and serve hot'
                ],
                'prep_time': 15,
                'cook_time': 25,
                'difficulty': 3,
                'servings': 5,
                'tags': ['chicken', 'fried', 'american', 'copycat'],
                'nutrition': {
                    'calories': 378,
                    'protein': 35.2,
                    'carbs': 28.5,
                    'fat': 14.8
                },
                'source_platform': 'tiktok',
                'source_url': 'https://www.tiktok.com/@thegoldenbalance/video/7515421268884098346',
                'video_thumbnail': 'https://picsum.photos/400/300?random=2',
                'tiktok_author': 'thegoldenbalance',
                'is_public': True,
                'user_id': 'system'
            },
            {
                'title': 'Classic Avocado Toast',
                'description': 'Simple, delicious, and healthy avocado toast with a twist',
                'ingredients': [
                    {'name': 'bread slices', 'quantity': '2'},
                    {'name': 'ripe avocado', 'quantity': '1'},
                    {'name': 'lime juice', 'quantity': '1 tbsp'},
                    {'name': 'salt', 'quantity': '1/2 tsp'},
                    {'name': 'red pepper flakes', 'quantity': '1/4 tsp'},
                    {'name': 'olive oil', 'quantity': '1 tsp'},
                    {'name': 'cherry tomatoes', 'quantity': '1/4 cup'}
                ],
                'instructions': [
                    'Toast bread until golden brown',
                    'Mash avocado with lime juice and salt',
                    'Spread avocado mixture on toast',
                    'Top with cherry tomatoes',
                    'Drizzle with olive oil',
                    'Sprinkle red pepper flakes on top'
                ],
                'prep_time': 5,
                'cook_time': 3,
                'difficulty': 1,
                'servings': 2,
                'tags': ['breakfast', 'healthy', 'vegan', 'quick'],
                'nutrition': {
                    'calories': 298,
                    'protein': 8.5,
                    'carbs': 32.0,
                    'fat': 16.5
                },
                'source_platform': 'instagram',
                'source_url': 'https://www.instagram.com/p/healthy_breakfast',
                'video_thumbnail': 'https://picsum.photos/400/300?random=3',
                'tiktok_author': None,
                'is_public': True,
                'user_id': 'system'
            },
            {
                'title': 'Chocolate Chip Cookies',
                'description': 'The perfect chewy chocolate chip cookies that everyone loves',
                'ingredients': [
                    {'name': 'butter', 'quantity': '1 cup'},
                    {'name': 'brown sugar', 'quantity': '3/4 cup'},
                    {'name': 'granulated sugar', 'quantity': '1/4 cup'},
                    {'name': 'eggs', 'quantity': '2'},
                    {'name': 'vanilla extract', 'quantity': '1 tsp'},
                    {'name': 'all-purpose flour', 'quantity': '2 1/4 cups'},
                    {'name': 'baking soda', 'quantity': '1 tsp'},
                    {'name': 'salt', 'quantity': '1 tsp'},
                    {'name': 'chocolate chips', 'quantity': '2 cups'}
                ],
                'instructions': [
                    'Preheat oven to 375°F',
                    'Cream butter and sugars together',
                    'Beat in eggs and vanilla',
                    'Mix in dry ingredients',
                    'Fold in chocolate chips',
                    'Drop onto baking sheet',
                    'Bake for 9-11 minutes'
                ],
                'prep_time': 15,
                'cook_time': 10,
                'difficulty': 2,
                'servings': 24,
                'tags': ['dessert', 'baking', 'cookies', 'chocolate'],
                'nutrition': {
                    'calories': 185,
                    'protein': 2.8,
                    'carbs': 24.5,
                    'fat': 9.2
                },
                'source_platform': 'youtube',
                'source_url': 'https://www.youtube.com/watch?v=cookie_recipe',
                'video_thumbnail': 'https://picsum.photos/400/300?random=4',
                'tiktok_author': None,
                'is_public': True,
                'user_id': 'system'
            },
            {
                'title': 'Spicy Thai Basil Beef',
                'description': 'Authentic Thai pad kra pao with ground beef and holy basil',
                'ingredients': [
                    {'name': 'ground beef', 'quantity': '1 lb'},
                    {'name': 'thai holy basil', 'quantity': '2 cups'},
                    {'name': 'garlic cloves', 'quantity': '6'},
                    {'name': 'thai chilies', 'quantity': '4'},
                    {'name': 'fish sauce', 'quantity': '2 tbsp'},
                    {'name': 'oyster sauce', 'quantity': '1 tbsp'},
                    {'name': 'soy sauce', 'quantity': '1 tbsp'},
                    {'name': 'palm sugar', 'quantity': '1 tsp'},
                    {'name': 'vegetable oil', 'quantity': '2 tbsp'}
                ],
                'instructions': [
                    'Heat oil in wok over high heat',
                    'Add garlic and chilies, stir-fry 30 seconds',
                    'Add ground beef, break up and cook',
                    'Add fish sauce, oyster sauce, soy sauce',
                    'Add palm sugar and stir',
                    'Add basil leaves and stir until wilted',
                    'Serve over rice with fried egg'
                ],
                'prep_time': 10,
                'cook_time': 8,
                'difficulty': 3,
                'servings': 4,
                'tags': ['thai', 'spicy', 'beef', 'authentic', 'dinner'],
                'nutrition': {
                    'calories': 312,
                    'protein': 28.5,
                    'carbs': 8.2,
                    'fat': 18.5
                },
                'source_platform': 'tiktok',
                'source_url': 'https://www.tiktok.com/@authentic_thai/video/thai_basil_beef',
                'video_thumbnail': 'https://picsum.photos/400/300?random=5',
                'tiktok_author': 'authentic_thai',
                'is_public': True,
                'user_id': 'system'
            }
        ]
        
        created_recipes = []
        for recipe_data in mock_recipes:
            recipe = recipe_service.create_recipe(recipe_data)
            created_recipes.append(recipe)
        
        return jsonify({
            'message': f'Successfully seeded {len(created_recipes)} recipes',
            'recipes': created_recipes
        }), 201
        
    except Exception as e:
        print(f"Error seeding recipes: {e}")
        return jsonify({
            'error': 'Failed to seed recipes',
            'message': 'An error occurred while seeding recipes.'
        }), 500


@recipe_bp.route('', methods=['POST'])
@jwt_required()
def create_recipe():
    """Create a new recipe"""
    try:
        # Get current user
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information.'
            }), 404
        
        # Validate input
        schema = CreateRecipeSchema()
        data = schema.load(request.get_json())
        
        # Add user_id to recipe data
        data['user_id'] = current_user['id']
        
        # Create recipe
        recipe = recipe_service.create_recipe(data)
        
        return jsonify({
            'message': 'Recipe created successfully',
            'recipe': recipe
        }), 201
        
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Invalid input data',
            'details': e.messages
        }), 400
    except Exception as e:
        print(f"Error creating recipe: {e}")
        return jsonify({
            'error': 'Failed to create recipe',
            'message': 'An error occurred while creating the recipe.'
        }), 500


# Error handlers
@recipe_bp.errorhandler(ValidationError)
def handle_validation_error(e):
    return jsonify({
        'error': 'Validation error',
        'message': 'Invalid input data',
        'details': e.messages
    }), 400


@recipe_bp.errorhandler(404)
def handle_not_found(e):
    return jsonify({
        'error': 'Resource not found',
        'message': 'The requested resource was not found.'
    }), 404


@recipe_bp.errorhandler(500)
def handle_internal_error(e):
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred. Please try again later.'
    }), 500

