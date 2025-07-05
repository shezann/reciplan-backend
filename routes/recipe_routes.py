from flask import request, jsonify
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.firestore_service import firestore_service
from marshmallow import Schema, fields, ValidationError

class RecipeSchema(Schema):
    """Schema for recipe validation"""
    title = fields.Str(required=True, validate=lambda x: len(x) >= 3)
    description = fields.Str(required=True)
    ingredients = fields.List(fields.Dict(), required=True)
    instructions = fields.List(fields.Str(), required=True)
    prep_time = fields.Int(required=True, validate=lambda x: x > 0)
    cook_time = fields.Int(required=True, validate=lambda x: x > 0)
    servings = fields.Int(required=True, validate=lambda x: x > 0)
    difficulty = fields.Str(validate=lambda x: x in ['easy', 'medium', 'hard'])
    tags = fields.List(fields.Str(), load_default=[])
    nutrition = fields.Dict(load_default={})
    is_public = fields.Bool(load_default=True)

class RecipeUpdateSchema(Schema):
    """Schema for recipe update validation"""
    title = fields.Str(validate=lambda x: len(x) >= 3)
    description = fields.Str()
    ingredients = fields.List(fields.Dict())
    instructions = fields.List(fields.Str())
    prep_time = fields.Int(validate=lambda x: x > 0)
    cook_time = fields.Int(validate=lambda x: x > 0)
    servings = fields.Int(validate=lambda x: x > 0)
    difficulty = fields.Str(validate=lambda x: x in ['easy', 'medium', 'hard'])
    tags = fields.List(fields.Str())
    nutrition = fields.Dict()
    is_public = fields.Bool()

class RecipeListResource(Resource):
    """Resource for handling recipe collection operations"""
    
    def get(self):
        """Get recipes (public recipes or user's recipes if authenticated)"""
        try:
            # Get query parameters
            limit = request.args.get('limit', type=int)
            tag = request.args.get('tag')
            difficulty = request.args.get('difficulty')
            user_id = request.args.get('user_id')
            
            # Build query based on parameters
            if user_id:
                # Get recipes by specific user
                recipes = firestore_service.query_collection('recipes', 'user_id', '==', user_id, limit=limit)
            elif tag:
                # Get recipes by tag
                recipes = firestore_service.query_collection('recipes', 'tags', 'array-contains', tag, limit=limit)
            elif difficulty:
                # Get recipes by difficulty
                recipes = firestore_service.query_collection('recipes', 'difficulty', '==', difficulty, limit=limit)
            else:
                # Get all public recipes
                recipes = firestore_service.query_collection('recipes', 'is_public', '==', True, limit=limit)
            
            return {'recipes': recipes}, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve recipes'}, 500
    
    @jwt_required()
    def post(self):
        """Create a new recipe"""
        try:
            current_user_id = get_jwt_identity()
            
            # Validate input data
            recipe_schema = RecipeSchema()
            data = recipe_schema.load(request.get_json())
            
            # Add user_id to recipe data
            data['user_id'] = current_user_id
            
            # Create recipe
            recipe_id = firestore_service.create_document('recipes', data)
            
            # Return created recipe
            recipe_data = data.copy()
            recipe_data['id'] = recipe_id
            
            return {'recipe': recipe_data}, 201
            
        except ValidationError as e:
            return {'error': 'Validation error', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Failed to create recipe'}, 500

class RecipeResource(Resource):
    """Resource for handling individual recipe operations"""
    
    def get(self, recipe_id):
        """Get a specific recipe"""
        try:
            # Get recipe from Firestore
            recipe = firestore_service.get_document('recipes', recipe_id)
            
            if not recipe:
                return {'error': 'Recipe not found'}, 404
            
            # Check if recipe is public or user has access
            from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
            try:
                verify_jwt_in_request()
                current_user_id = get_jwt_identity()
                user_has_access = current_user_id == recipe.get('user_id')
            except:
                user_has_access = False
            
            if not recipe.get('is_public', True) and not user_has_access:
                return {'error': 'Access denied'}, 403
            
            return {'recipe': recipe}, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve recipe'}, 500
    
    @jwt_required()
    def put(self, recipe_id):
        """Update a recipe"""
        try:
            current_user_id = get_jwt_identity()
            
            # Check if recipe exists and user owns it
            existing_recipe = firestore_service.get_document('recipes', recipe_id)
            if not existing_recipe:
                return {'error': 'Recipe not found'}, 404
            
            if existing_recipe.get('user_id') != current_user_id:
                return {'error': 'Unauthorized'}, 403
            
            # Validate input data
            recipe_schema = RecipeUpdateSchema()
            data = recipe_schema.load(request.get_json())
            
            # Update recipe
            success = firestore_service.update_document('recipes', recipe_id, data)
            
            if not success:
                return {'error': 'Failed to update recipe'}, 500
            
            # Return updated recipe
            updated_recipe = firestore_service.get_document('recipes', recipe_id)
            
            return {'recipe': updated_recipe}, 200
            
        except ValidationError as e:
            return {'error': 'Validation error', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Failed to update recipe'}, 500
    
    @jwt_required()
    def delete(self, recipe_id):
        """Delete a recipe"""
        try:
            current_user_id = get_jwt_identity()
            
            # Check if recipe exists and user owns it
            existing_recipe = firestore_service.get_document('recipes', recipe_id)
            if not existing_recipe:
                return {'error': 'Recipe not found'}, 404
            
            if existing_recipe.get('user_id') != current_user_id:
                return {'error': 'Unauthorized'}, 403
            
            # Delete recipe
            success = firestore_service.delete_document('recipes', recipe_id)
            
            if not success:
                return {'error': 'Failed to delete recipe'}, 500
            
            return {'message': 'Recipe deleted successfully'}, 200
            
        except Exception as e:
            return {'error': 'Failed to delete recipe'}, 500 