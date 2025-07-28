"""
Like controller for handling recipe like/unlike operations
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from services.like_service import (
    like_service, 
    LikeServiceError, 
    RecipeNotFoundError, 
    UserNotFoundError, 
    InvalidInputError, 
    PermissionDeniedError, 
    RecipeNotAvailableError
)
from services.jwt_service import get_user_from_token
from schemas.like import LikeResponseSchema, LikeStatusSchema


# Create blueprint for like operations
like_bp = Blueprint('like', __name__, url_prefix='/api/recipes')


@like_bp.route('/<recipe_id>/like', methods=['POST'])
@jwt_required()
def like_recipe(recipe_id):
    """
    Like a recipe
    
    Args:
        recipe_id: The recipe ID to like
        
    Returns:
        JSON response with like status and count
        
    Responses:
        200: Successfully liked/already liked
        400: Invalid input or operation
        401: Unauthorized (handled by @jwt_required)
        403: Permission denied (banned user, private recipe)
        404: Recipe or user not found
        422: Recipe not available (draft, processing)
        500: Internal server error
    """
    try:
        # Validate Content-Type for POST requests
        if request.content_type and 'application/json' not in request.content_type:
            return jsonify({
                'error': 'Invalid Content-Type',
                'message': 'Content-Type must be application/json for POST requests.'
            }), 400
        
        # Handle JSON payload if present (though not required for this endpoint)
        if request.is_json:
            try:
                request_data = request.get_json()
                if request_data is not None and not isinstance(request_data, dict):
                    return jsonify({
                        'error': 'Invalid JSON',
                        'message': 'JSON payload must be an object.'
                    }), 400
            except Exception:
                return jsonify({
                    'error': 'Malformed JSON',
                    'message': 'Invalid JSON format in request body.'
                }), 400
        
        # Get current user from JWT token
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information from token.'
            }), 404
        
        user_id = current_user['id']
        
        # Call like service to toggle like (like=True)
        result = like_service.toggle_like(recipe_id, user_id, like=True)
        
        # Format response using schema
        response_data = {
            'liked': result['liked'],
            'likes_count': result['likes_count'],
            'recipe_id': recipe_id,
            'user_id': user_id,
            'timestamp': result['timestamp']
        }
        
        # Validate and serialize response
        schema = LikeResponseSchema()
        validated_response = schema.dump(response_data)
        
        return jsonify(validated_response), 200
        
    except InvalidInputError as e:
        return jsonify({
            'error': 'Invalid input',
            'message': str(e)
        }), 400
    except UserNotFoundError as e:
        return jsonify({
            'error': 'User not found',
            'message': str(e)
        }), 404
    except RecipeNotFoundError as e:
        return jsonify({
            'error': 'Recipe not found',
            'message': str(e)
        }), 404
    except RecipeNotAvailableError as e:
        return jsonify({
            'error': 'Recipe not available',
            'message': str(e)
        }), 422
    except PermissionDeniedError as e:
        return jsonify({
            'error': 'Permission denied',
            'message': str(e)
        }), 403
    except LikeServiceError as e:
        return jsonify({
            'error': 'Service error',
            'message': str(e)
        }), 500
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Response data validation failed',
            'details': e.messages
        }), 500
    except Exception as e:
        print(f"[LikeController] Unexpected error liking recipe {recipe_id}: {e}")
        return jsonify({
            'error': 'Failed to like recipe',
            'message': 'An unexpected error occurred while liking the recipe.'
        }), 500


@like_bp.route('/<recipe_id>/like', methods=['DELETE'])
@jwt_required()
def unlike_recipe(recipe_id):
    """
    Unlike a recipe
    
    Args:
        recipe_id: The recipe ID to unlike
        
    Returns:
        JSON response with like status and count
        
    Responses:
        200: Successfully unliked/already not liked
        400: Invalid input or operation
        401: Unauthorized (handled by @jwt_required)
        403: Permission denied (banned user, private recipe)
        404: Recipe or user not found
        422: Recipe not available (draft, processing)
        500: Internal server error
    """
    try:
        # Get current user from JWT token
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information from token.'
            }), 404
        
        user_id = current_user['id']
        
        # Call like service to toggle like (like=False)
        result = like_service.toggle_like(recipe_id, user_id, like=False)
        
        # Format response using schema
        response_data = {
            'liked': result['liked'],
            'likes_count': result['likes_count'],
            'recipe_id': recipe_id,
            'user_id': user_id,
            'timestamp': result['timestamp']
        }
        
        # Validate and serialize response
        schema = LikeResponseSchema()
        validated_response = schema.dump(response_data)
        
        return jsonify(validated_response), 200
        
    except InvalidInputError as e:
        return jsonify({
            'error': 'Invalid input',
            'message': str(e)
        }), 400
    except UserNotFoundError as e:
        return jsonify({
            'error': 'User not found',
            'message': str(e)
        }), 404
    except RecipeNotFoundError as e:
        return jsonify({
            'error': 'Recipe not found',
            'message': str(e)
        }), 404
    except RecipeNotAvailableError as e:
        return jsonify({
            'error': 'Recipe not available',
            'message': str(e)
        }), 422
    except PermissionDeniedError as e:
        return jsonify({
            'error': 'Permission denied',
            'message': str(e)
        }), 403
    except LikeServiceError as e:
        return jsonify({
            'error': 'Service error',
            'message': str(e)
        }), 500
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Response data validation failed',
            'details': e.messages
        }), 500
    except Exception as e:
        print(f"[LikeController] Unexpected error unliking recipe {recipe_id}: {e}")
        return jsonify({
            'error': 'Failed to unlike recipe',
            'message': 'An unexpected error occurred while unliking the recipe.'
        }), 500


@like_bp.route('/<recipe_id>/liked', methods=['GET'])
@jwt_required()
def get_like_status(recipe_id):
    """
    Check if current user has liked a recipe
    
    Args:
        recipe_id: The recipe ID to check
        
    Returns:
        JSON response with like status
        
    Responses:
        200: Successfully retrieved like status
        400: Invalid input
        401: Unauthorized (handled by @jwt_required)
        404: Recipe or user not found
        500: Internal server error
    """
    try:
        # Get current user from JWT token
        current_user = get_user_from_token()
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'Could not find user information from token.'
            }), 404
        
        user_id = current_user['id']
        
        # Get like status from service
        liked = like_service.has_liked(recipe_id, user_id)
        
        # Check if recipe exists (has_liked returns None for non-existent recipes)
        if liked is None:
            return jsonify({
                'error': 'Recipe not found',
                'message': 'The specified recipe does not exist or is not available.'
            }), 404
        
        # Format response using schema
        response_data = {
            'liked': liked,
            'recipe_id': recipe_id,
            'user_id': user_id
        }
        
        # Validate and serialize response
        schema = LikeStatusSchema()
        validated_response = schema.dump(response_data)
        
        return jsonify(validated_response), 200
        
    except InvalidInputError as e:
        return jsonify({
            'error': 'Invalid input',
            'message': str(e)
        }), 400
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Response data validation failed',
            'details': e.messages
        }), 500
    except Exception as e:
        print(f"[LikeController] Unexpected error getting like status for recipe {recipe_id}: {e}")
        return jsonify({
            'error': 'Failed to get like status',
            'message': 'An unexpected error occurred while checking like status.'
        }), 500


# Error handlers for the like blueprint
@like_bp.errorhandler(400)
def handle_bad_request(e):
    """Handle 400 Bad Request errors"""
    return jsonify({
        'error': 'Bad request',
        'message': 'The request could not be processed due to invalid input.'
    }), 400


@like_bp.errorhandler(403)
def handle_forbidden(e):
    """Handle 403 Forbidden errors"""
    return jsonify({
        'error': 'Forbidden',
        'message': 'You do not have permission to perform this action.'
    }), 403


@like_bp.errorhandler(404)
def handle_not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Resource not found',
        'message': 'The requested resource was not found.'
    }), 404


@like_bp.errorhandler(422)
def handle_unprocessable_entity(e):
    """Handle 422 Unprocessable Entity errors"""
    return jsonify({
        'error': 'Unprocessable entity',
        'message': 'The request is well-formed but contains invalid data.'
    }), 422


@like_bp.errorhandler(500)
def handle_internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred. Please try again later.'
    }), 500


@like_bp.errorhandler(ValidationError)
def handle_validation_error(e):
    """Handle Marshmallow validation errors"""
    return jsonify({
        'error': 'Validation error',
        'message': 'Invalid input data',
        'details': e.messages
    }), 400 